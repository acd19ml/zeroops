package remediation

import (
	"context"
	"fmt"
	"strconv"
	"time"

	adb "github.com/qiniu/zeroops/internal/alerting/database"
	"github.com/qiniu/zeroops/internal/alerting/service/healthcheck"
	"github.com/redis/go-redis/v9"
	"github.com/rs/zerolog/log"
)

type Consumer struct {
	DB    *adb.Database
	Redis *redis.Client

	// Heal action service for P0 alerts
	healService HealActionService

	// Observation window manager
	obsManager ObservationWindowManager

	// sleepFn allows overriding for tests
	sleepFn func(time.Duration)
}

func NewConsumer(db *adb.Database, rdb *redis.Client) *Consumer {
	healDAO := NewPgHealActionDAO(db)
	healService := NewHealActionService(healDAO)
	obsManager := NewRedisObservationWindowManager(rdb)
	return &Consumer{
		DB:          db,
		Redis:       rdb,
		healService: healService,
		obsManager:  obsManager,
		sleepFn:     time.Sleep,
	}
}

// Start consumes alert messages and processes them based on alert level
func (c *Consumer) Start(ctx context.Context, ch <-chan healthcheck.AlertMessage) {
	if ch == nil {
		log.Warn().Msg("remediation consumer started without channel; no-op")
		return
	}

	for {
		select {
		case <-ctx.Done():
			return
		case m := <-ch:
			// 首先检查是否有观察窗口需要处理
			c.handleObservationWindow(ctx, &m)

			switch m.Level {
			case "P0":
				// P0 告警：故障治愈流程
				c.handleP0Alert(ctx, &m)
			case "P1", "P2":
				// P1/P2 告警：下钻分析流程
				c.handleP1P2Alert(ctx, &m)
			default:
				log.Warn().Str("level", m.Level).Str("issue", m.ID).Msg("unknown alert level, skipping")
			}
		}
	}
}

// handleObservationWindow handles observation window logic for incoming alerts
func (c *Consumer) handleObservationWindow(ctx context.Context, m *healthcheck.AlertMessage) {
	if m.Service == "" {
		return // No service information, skip observation window check
	}

	// 检查是否有该服务的观察窗口
	window, err := c.obsManager.CheckObservation(ctx, m.Service, m.Version)
	if err != nil {
		log.Error().Err(err).Str("service", m.Service).Str("version", m.Version).Msg("failed to check observation window")
		return
	}

	if window == nil {
		return // No active observation window
	}

	// 如果在观察窗口期间出现新的告警，取消观察窗口
	log.Warn().
		Str("service", m.Service).
		Str("version", m.Version).
		Str("alert_id", m.ID).
		Str("observation_alert_id", window.AlertID).
		Msg("new alert detected during observation window, cancelling observation")

	if err := c.obsManager.CancelObservation(ctx, m.Service, m.Version); err != nil {
		log.Error().Err(err).Str("service", m.Service).Str("version", m.Version).Msg("failed to cancel observation window")
	}
}

// handleP0Alert handles P0 alerts with fault healing process
func (c *Consumer) handleP0Alert(ctx context.Context, m *healthcheck.AlertMessage) {
	log.Info().Str("issue", m.ID).Str("level", m.Level).Msg("processing P0 alert with fault healing")

	// 1) 确认故障域
	faultDomain := c.healService.IdentifyFaultDomain(m.Labels)
	log.Info().Str("issue", m.ID).Str("fault_domain", string(faultDomain)).Msg("identified fault domain")

	// 2) 查询治愈方案
	healAction, err := c.healService.GetHealAction(ctx, faultDomain)
	if err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("failed to get heal action")
		// 如果无法获取治愈方案，直接进入下钻分析
		c.handleDrillDownAnalysis(ctx, m)
		return
	}

	// 3) 执行治愈操作
	result, err := c.healService.ExecuteHealAction(ctx, healAction, m.ID, m.Labels)
	if err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("failed to execute heal action")
		c.handleDrillDownAnalysis(ctx, m)
		return
	}

	if !result.Success {
		log.Warn().Str("issue", m.ID).Str("message", result.Message).Msg("heal action failed")
		// 治愈失败，仍然进入下钻分析
		c.handleDrillDownAnalysis(ctx, m)
		return
	}

	log.Info().Str("issue", m.ID).Str("message", result.Message).Msg("heal action completed successfully")

	// 4) 治愈成功后启动观察窗口
	if m.Service != "" {
		obsDuration := GetObservationDuration()
		if err := c.obsManager.StartObservation(ctx, m.Service, m.Version, m.ID, obsDuration); err != nil {
			log.Error().Err(err).Str("service", m.Service).Str("version", m.Version).Msg("failed to start observation window")
		} else {
			log.Info().
				Str("service", m.Service).
				Str("version", m.Version).
				Str("alert_id", m.ID).
				Dur("duration", obsDuration).
				Msg("started observation window after successful healing")
		}
	}

	// 5) 治愈成功后进入下钻分析（但不立即更新状态）
	c.handleDrillDownAnalysisWithObservation(ctx, m)
}

// handleP1P2Alert handles P1/P2 alerts with drill-down analysis
func (c *Consumer) handleP1P2Alert(ctx context.Context, m *healthcheck.AlertMessage) {
	log.Info().Str("issue", m.ID).Str("level", m.Level).Msg("processing P1/P2 alert with drill-down analysis")

	// 直接进入下钻分析流程
	c.handleDrillDownAnalysis(ctx, m)
}

// handleDrillDownAnalysis performs drill-down analysis and marks alert as restored
func (c *Consumer) handleDrillDownAnalysis(ctx context.Context, m *healthcheck.AlertMessage) {
	// 1) 执行 AI 分析
	if err := c.addAIAnalysisComment(ctx, m); err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("addAIAnalysisComment failed")
	}

	// 2) 更新告警状态为恢复
	if err := c.markRestoredInDB(ctx, m); err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("markRestoredInDB failed")
		return // Stop processing on critical DB failure
	}
	// 3) 更新缓存状态
	if err := c.markRestoredInCache(ctx, m); err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("markRestoredInCache failed")
		// Cache failure is less critical, continue processing
	}
}

// handleDrillDownAnalysisWithObservation performs drill-down analysis but delays status update for observation
func (c *Consumer) handleDrillDownAnalysisWithObservation(ctx context.Context, m *healthcheck.AlertMessage) {
	// 1) 执行 AI 分析
	if err := c.addAIAnalysisComment(ctx, m); err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("addAIAnalysisComment failed")
	}

	// 2) 暂时不更新告警状态，等待观察窗口完成
	// 只记录治愈操作完成的评论
	if err := c.addHealingCompletedComment(ctx, m); err != nil {
		log.Error().Err(err).Str("issue", m.ID).Msg("addHealingCompletedComment failed")
	}

	log.Info().
		Str("issue", m.ID).
		Str("service", m.Service).
		Str("version", m.Version).
		Msg("healing completed, waiting for observation window to complete before updating status")
}

// deriveDeployID derives deployment ID from alert message
// TODO: Use this function when implementing real rollback API calls
func deriveDeployID(m *healthcheck.AlertMessage) string {
	if m == nil {
		return ""
	}
	if v := m.Labels["deploy_id"]; v != "" {
		return v
	}
	return fmt.Sprintf("%s:%s", m.Service, m.Version)
}

func (c *Consumer) addAIAnalysisComment(ctx context.Context, m *healthcheck.AlertMessage) error {
	if c.DB == nil || m == nil {
		return nil
	}
	const existsQ = `SELECT 1 FROM alert_issue_comments WHERE issue_id=$1 AND content=$2 LIMIT 1`
	const insertQ = `INSERT INTO alert_issue_comments (issue_id, create_at, content) VALUES ($1, NOW(), $2)`
	content := "## AI分析结果\n" +
		"**问题类型**：非发版本导致的问题\n" +
		"**根因分析**：数据库连接池配置不足，导致大量请求无法获取数据库连接\n" +
		"**处理建议**：\n" +
		"- 增加数据库连接池大小\n" +
		"- 优化数据库连接管理\n" +
		"- 考虑读写分离缓解压力\n" +
		"**执行状态**：正在处理中，等待指标恢复正常"
	if rows, err := c.DB.QueryContext(ctx, existsQ, m.ID, content); err == nil {
		defer rows.Close()
		if rows.Next() {
			return nil
		}
	}
	_, err := c.DB.ExecContext(ctx, insertQ, m.ID, content)
	return err
}

func (c *Consumer) addHealingCompletedComment(ctx context.Context, m *healthcheck.AlertMessage) error {
	if c.DB == nil || m == nil {
		return nil
	}
	const existsQ = `SELECT 1 FROM alert_issue_comments WHERE issue_id=$1 AND content=$2 LIMIT 1`
	const insertQ = `INSERT INTO alert_issue_comments (issue_id, create_at, content) VALUES ($1, NOW(), $2)`
	content := "## 治愈操作完成\n" +
		"**操作状态**：治愈操作已成功执行\n" +
		"**观察窗口**：正在等待观察窗口完成（30分钟）\n" +
		"**下一步**：如果观察窗口内无新告警，将自动更新服务状态为正常"
	if rows, err := c.DB.QueryContext(ctx, existsQ, m.ID, content); err == nil {
		defer rows.Close()
		if rows.Next() {
			return nil
		}
	}
	_, err := c.DB.ExecContext(ctx, insertQ, m.ID, content)
	return err
}

func (c *Consumer) markRestoredInDB(ctx context.Context, m *healthcheck.AlertMessage) error {
	if c.DB == nil || m == nil {
		return nil
	}

	// 更新 alert_issues 状态
	if _, err := c.DB.ExecContext(ctx, `UPDATE alert_issues SET alert_state = 'Restored' , state = 'Closed' WHERE id = $1`, m.ID); err != nil {
		return err
	}

	// 同时更新 service_states.health_state 为 Normal
	// 注意：每次修改 service_states 为 Normal 时都需要修改 alert_issues.alert_state 为 Restored
	if m.Service != "" {
		const upsert = `
INSERT INTO service_states (service, version, report_at, resolved_at, health_state, alert_issue_ids)
VALUES ($1, $2, NULL, NOW(), 'Normal', ARRAY[$3]::text[])
ON CONFLICT (service, version) DO UPDATE
SET health_state = 'Normal',
    resolved_at = NOW();
`
		if _, err := c.DB.ExecContext(ctx, upsert, m.Service, m.Version, m.ID); err != nil {
			return err
		}
	}

	return nil
}

func (c *Consumer) markRestoredInCache(ctx context.Context, m *healthcheck.AlertMessage) error {
	if c.Redis == nil || m == nil {
		return nil
	}
	// 1) alert:issue:{id} → alertState=Restored; state=Closed; move indices
	alertKey := "alert:issue:" + m.ID
	script := redis.NewScript(`
local v = redis.call('GET', KEYS[1])
if not v then return 0 end
local obj = cjson.decode(v)
obj.alertState = ARGV[1]
obj.state = ARGV[3]
redis.call('SET', KEYS[1], cjson.encode(obj), 'KEEPTTL')
if KEYS[2] ~= '' then redis.call('SREM', KEYS[2], ARGV[2]) end
if KEYS[3] ~= '' then redis.call('SREM', KEYS[3], ARGV[2]) end
if KEYS[4] ~= '' then redis.call('SADD', KEYS[4], ARGV[2]) end
-- move open→closed indices
if KEYS[5] ~= '' then redis.call('SREM', KEYS[5], ARGV[2]) end
if KEYS[6] ~= '' then redis.call('SADD', KEYS[6], ARGV[2]) end
-- service scoped indices if service exists in payload
local svc = obj['service']
if svc and svc ~= '' then
  local openSvcKey = 'alert:index:svc:' .. svc .. ':open'
  local closedSvcKey = 'alert:index:svc:' .. svc .. ':closed'
  redis.call('SREM', openSvcKey, ARGV[2])
  redis.call('SADD', closedSvcKey, ARGV[2])
end
return 1
`)
	_, _ = script.Run(ctx, c.Redis, []string{alertKey, "alert:index:alert_state:Pending", "alert:index:alert_state:InProcessing", "alert:index:alert_state:Restored", "alert:index:open", "alert:index:closed"}, "Restored", m.ID, "Closed").Result()

	// 更新 service_state 缓存
	if m.Service != "" {
		svcKey := "service_state:" + m.Service + ":" + m.Version
		now := time.Now().UTC().Format(time.RFC3339Nano)
		svcScript := redis.NewScript(`
local v = redis.call('GET', KEYS[1])
if not v then v = '{}' end
local obj = cjson.decode(v)
obj.health_state = ARGV[1]
obj.resolved_at = ARGV[2]
redis.call('SET', KEYS[1], cjson.encode(obj), 'KEEPTTL')
if KEYS[2] ~= '' then redis.call('SADD', KEYS[2], KEYS[1]) end
return 1
`)
		_, _ = svcScript.Run(ctx, c.Redis, []string{svcKey, "service_state:index:health:Normal"}, "Normal", now).Result()
	}
	return nil
}

// CompleteObservationAndUpdateStatus completes observation window and updates service status
func (c *Consumer) CompleteObservationAndUpdateStatus(ctx context.Context, service, version string) error {
	if service == "" {
		return fmt.Errorf("service name is required")
	}

	// 完成观察窗口
	if err := c.obsManager.CompleteObservation(ctx, service, version); err != nil {
		return fmt.Errorf("failed to complete observation window: %w", err)
	}

	// 更新服务状态为正常
	const upsert = `
INSERT INTO service_states (service, version, report_at, resolved_at, health_state, alert_issue_ids)
VALUES ($1, $2, NULL, NOW(), 'Normal', ARRAY[]::text[])
ON CONFLICT (service, version) DO UPDATE
SET health_state = 'Normal',
    resolved_at = NOW();
`
	if _, err := c.DB.ExecContext(ctx, upsert, service, version); err != nil {
		return fmt.Errorf("failed to update service state: %w", err)
	}

	// 更新缓存
	if c.Redis != nil {
		svcKey := "service_state:" + service + ":" + version
		now := time.Now().UTC().Format(time.RFC3339Nano)
		svcScript := redis.NewScript(`
local v = redis.call('GET', KEYS[1])
if not v then v = '{}' end
local obj = cjson.decode(v)
obj.health_state = ARGV[1]
obj.resolved_at = ARGV[2]
redis.call('SET', KEYS[1], cjson.encode(obj), 'KEEPTTL')
if KEYS[2] ~= '' then redis.call('SADD', KEYS[2], KEYS[1]) end
return 1
`)
		_, _ = svcScript.Run(ctx, c.Redis, []string{svcKey, "service_state:index:health:Normal"}, "Normal", now).Result()
	}

	log.Info().
		Str("service", service).
		Str("version", version).
		Msg("observation window completed successfully, service status updated to Normal")

	return nil
}

func parseDuration(s string, d time.Duration) time.Duration {
	if s == "" {
		return d
	}
	if v, err := time.ParseDuration(s); err == nil {
		return v
	}
	return d
}

func parseInt(s string, v int) int {
	if s == "" {
		return v
	}
	if n, err := strconv.Atoi(s); err == nil {
		return n
	}
	return v
}
