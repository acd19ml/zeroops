package remediation

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/rs/zerolog/log"
)

// RedisObservationWindowManager implements ObservationWindowManager using Redis
type RedisObservationWindowManager struct {
	redis *redis.Client
}

// NewRedisObservationWindowManager creates a new Redis-based observation window manager
func NewRedisObservationWindowManager(redis *redis.Client) *RedisObservationWindowManager {
	return &RedisObservationWindowManager{redis: redis}
}

// StartObservation starts an observation window for a service
func (m *RedisObservationWindowManager) StartObservation(ctx context.Context, service, version, alertID string, duration time.Duration) error {
	if m.redis == nil {
		return fmt.Errorf("redis client is nil")
	}

	now := time.Now()
	window := &ObservationWindow{
		Duration:  duration,
		Service:   service,
		Version:   version,
		AlertID:   alertID,
		StartTime: now,
		EndTime:   now.Add(duration),
		IsActive:  true,
	}

	key := fmt.Sprintf("observation:%s:%s", service, version)
	data, err := json.Marshal(window)
	if err != nil {
		return fmt.Errorf("failed to marshal observation window: %w", err)
	}

	// Store with TTL equal to observation duration + buffer
	ttl := duration + 5*time.Minute
	err = m.redis.Set(ctx, key, data, ttl).Err()
	if err != nil {
		return fmt.Errorf("failed to store observation window: %w", err)
	}

	log.Info().
		Str("service", service).
		Str("version", version).
		Str("alert_id", alertID).
		Dur("duration", duration).
		Time("end_time", window.EndTime).
		Msg("started observation window")

	return nil
}

// CheckObservation checks if there's an active observation window for a service
func (m *RedisObservationWindowManager) CheckObservation(ctx context.Context, service, version string) (*ObservationWindow, error) {
	if m.redis == nil {
		return nil, fmt.Errorf("redis client is nil")
	}

	key := fmt.Sprintf("observation:%s:%s", service, version)
	data, err := m.redis.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, nil // No active observation window
		}
		return nil, fmt.Errorf("failed to get observation window: %w", err)
	}

	var window ObservationWindow
	err = json.Unmarshal([]byte(data), &window)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal observation window: %w", err)
	}

	// Check if observation window has expired (atomic operation)
	if time.Now().After(window.EndTime) {
		// Clean up expired window atomically
		if err := m.redis.Del(ctx, key).Err(); err != nil {
			return nil, fmt.Errorf("failed to clean up expired observation window: %w", err)
		}
		return nil, nil
	}

	return &window, nil
}

// CompleteObservation completes an observation window and marks it as successful
func (m *RedisObservationWindowManager) CompleteObservation(ctx context.Context, service, version string) error {
	if m.redis == nil {
		return fmt.Errorf("redis client is nil")
	}

	key := fmt.Sprintf("observation:%s:%s", service, version)

	// Get the current window
	window, err := m.CheckObservation(ctx, service, version)
	if err != nil {
		return fmt.Errorf("failed to check observation window: %w", err)
	}

	if window == nil {
		return fmt.Errorf("no active observation window found for service %s version %s", service, version)
	}

	// Mark as completed and remove from Redis
	window.IsActive = false
	err = m.redis.Del(ctx, key).Err()
	if err != nil {
		return fmt.Errorf("failed to remove observation window: %w", err)
	}

	log.Info().
		Str("service", service).
		Str("version", version).
		Str("alert_id", window.AlertID).
		Dur("duration", window.Duration).
		Msg("completed observation window successfully")

	return nil
}

// CancelObservation cancels an observation window due to new alerts
func (m *RedisObservationWindowManager) CancelObservation(ctx context.Context, service, version string) error {
	if m.redis == nil {
		return fmt.Errorf("redis client is nil")
	}

	key := fmt.Sprintf("observation:%s:%s", service, version)

	// Get the current window for logging
	window, err := m.CheckObservation(ctx, service, version)
	if err != nil {
		return fmt.Errorf("failed to check observation window: %w", err)
	}

	if window == nil {
		return nil // No active window to cancel
	}

	// Remove the observation window
	err = m.redis.Del(ctx, key).Err()
	if err != nil {
		return fmt.Errorf("failed to cancel observation window: %w", err)
	}

	log.Warn().
		Str("service", service).
		Str("version", version).
		Str("alert_id", window.AlertID).
		Msg("cancelled observation window due to new alerts")

	return nil
}

// GetObservationDuration returns the configured observation duration
// TODO: 后续可以从配置或数据库中动态获取观察时间
func GetObservationDuration() time.Duration {
	// 暂时使用固定的30分钟观察窗口
	// 后续可以扩展为从环境变量或配置文件中读取
	return 30 * time.Minute
}
