package service

import (
	"fmt"
	"net/http"
	"os"
	"strings"

	deployModel "github.com/qiniu/zeroops/internal/deploy/model"
	deployService "github.com/qiniu/zeroops/internal/deploy/service"
	"github.com/qiniu/zeroops/internal/service_manager/model"
)

// DeployAdapter 部署适配器，处理 service_manager 和 deploy 模块间的参数转换
type DeployAdapter struct {
	instanceManager deployService.InstanceManager
	baseURL         string // 包仓库基础URL
}

// NewDeployAdapter 创建部署适配器
func NewDeployAdapter(instanceManager deployService.InstanceManager) *DeployAdapter {
	return &DeployAdapter{
		instanceManager: instanceManager,
		baseURL:         "/tmp/zeroops/packages", // 包仓库路径（10.210.10.33）
	}
}

// BuildDeployNewServiceParams 构建新服务部署参数
func (a *DeployAdapter) BuildDeployNewServiceParams(req *model.CreateDeploymentRequest) (*deployModel.DeployNewServiceParams, error) {
	// 确定实例数量
	instanceCount := a.determineInstanceCount(req)

	// 构建包URL
	packageURL := a.buildPackageURL(req.Service, req.Version, req.PackageURL)

	return &deployModel.DeployNewServiceParams{
		Service:    req.Service,
		Version:    req.Version,
		TotalNum:   instanceCount,
		PackageURL: packageURL,
	}, nil
}

// BuildDeployNewVersionParams 构建版本升级参数
func (a *DeployAdapter) BuildDeployNewVersionParams(req *model.CreateDeploymentRequest) (*deployModel.DeployNewVersionParams, error) {
	// 获取服务的现有实例
	instances, err := a.instanceManager.GetServiceInstances(req.Service)
	if err != nil {
		return nil, fmt.Errorf("failed to get service instances: %w", err)
	}

	if len(instances) == 0 {
		return nil, fmt.Errorf("no existing instances found for service %s", req.Service)
	}

	// 提取实例ID列表
	instanceIDs := make([]string, len(instances))
	for i, inst := range instances {
		instanceIDs[i] = inst.InstanceID
	}

	// 构建包URL
	packageURL := a.buildPackageURL(req.Service, req.Version, req.PackageURL)

	return &deployModel.DeployNewVersionParams{
		Service:    req.Service,
		Version:    req.Version,
		Instances:  instanceIDs,
		PackageURL: packageURL,
	}, nil
}

// BuildRollbackParams 构建回滚参数
func (a *DeployAdapter) BuildRollbackParams(deployment *model.Deployment, req *model.RollbackDeploymentRequest) (*deployModel.RollbackParams, error) {
	// 获取当前部署涉及的实例
	instances, err := a.instanceManager.GetServiceInstances(deployment.Service, deployment.Version)
	if err != nil {
		return nil, fmt.Errorf("failed to get service instances for rollback: %w", err)
	}

	if len(instances) == 0 {
		return nil, fmt.Errorf("no instances found for service %s version %s", deployment.Service, deployment.Version)
	}

	// 提取实例ID列表
	instanceIDs := make([]string, len(instances))
	for i, inst := range instances {
		instanceIDs[i] = inst.InstanceID
	}

	// 构建回滚包URL
	packageURL := a.buildPackageURL(deployment.Service, req.TargetVersion, req.PackageURL)

	return &deployModel.RollbackParams{
		Service:       deployment.Service,
		TargetVersion: req.TargetVersion,
		Instances:     instanceIDs,
		PackageURL:    packageURL,
	}, nil
}

// determineInstanceCount 确定实例数量
func (a *DeployAdapter) determineInstanceCount(req *model.CreateDeploymentRequest) int {
	// 如果请求中指定了实例数量，使用指定值
	if req.InstanceCount > 0 {
		return req.InstanceCount
	}

	// 否则使用默认值
	return 1
}

// buildPackageURL 构建包下载URL
// 规则：
// 1. 固定从 /tmp/zeroops/packages 路径获取
// 2. 服务名去掉 -service 后缀（如果有）
// 3. 固定使用版本 v1.0.0
// 4. 格式：/tmp/zeroops/packages/{处理后的服务名}-v1.0.0.tar.gz
func (a *DeployAdapter) buildPackageURL(serviceName, version, customURL string) string {
	// 处理服务名：去掉 -service 后缀
	processedServiceName := strings.TrimSuffix(serviceName, "-service")

	// 固定路径和版本，构建包文件路径
	// 格式：/tmp/zeroops/packages/{service}-v1.0.0.tar.gz
	return fmt.Sprintf("%s/%s-v1.0.0.tar.gz",
		a.baseURL, processedServiceName)
}

// ValidatePackageURL 验证包URL是否有效
func (a *DeployAdapter) ValidatePackageURL(packageURL string) error {
	// 调用 deploy 模块的验证函数
	if err := deployService.ValidatePackageURL(packageURL); err != nil {
		return err
	}

	// 区分HTTP URL和本地文件路径
	if strings.HasPrefix(packageURL, "http://") || strings.HasPrefix(packageURL, "https://") {
		// HTTP URL检查
		resp, err := http.Head(packageURL)
		if err != nil {
			return fmt.Errorf("package URL not accessible: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != 200 {
			return fmt.Errorf("package not found: HTTP %d", resp.StatusCode)
		}
	} else {
		// 本地文件路径检查
		if _, err := os.Stat(packageURL); err != nil {
			if os.IsNotExist(err) {
				return fmt.Errorf("package file not found: %s", packageURL)
			}
			return fmt.Errorf("package file not accessible: %w", err)
		}
	}

	return nil
}

// IsNewServiceDeployment 判断是否为新服务部署
func (a *DeployAdapter) IsNewServiceDeployment(serviceName string) (bool, error) {
	instances, err := a.instanceManager.GetServiceInstances(serviceName)
	if err != nil {
		return false, fmt.Errorf("failed to check existing instances: %w", err)
	}

	// 如果没有现有实例，则为新服务部署
	return len(instances) == 0, nil
}
