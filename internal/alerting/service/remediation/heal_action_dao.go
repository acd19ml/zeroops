package remediation

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"

	adb "github.com/qiniu/zeroops/internal/alerting/database"
)

// PgHealActionDAO implements HealActionDAO using PostgreSQL
type PgHealActionDAO struct {
	DB *adb.Database
}

// NewPgHealActionDAO creates a new PostgreSQL heal action DAO
func NewPgHealActionDAO(db *adb.Database) *PgHealActionDAO {
	return &PgHealActionDAO{DB: db}
}

// GetByType retrieves a heal action by fault domain type
func (d *PgHealActionDAO) GetByType(ctx context.Context, faultType string) (*HealAction, error) {
	const q = `SELECT id, desc, type, rules FROM heal_actions WHERE type = $1`

	row := d.DB.QueryRowContext(ctx, q, faultType)
	var action HealAction
	var rulesJSON string

	err := row.Scan(&action.ID, &action.Desc, &action.Type, &rulesJSON)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("no heal action found for type: %s", faultType)
		}
		return nil, fmt.Errorf("failed to get heal action by type: %w", err)
	}

	action.Rules = json.RawMessage(rulesJSON)
	return &action, nil
}

// GetByID retrieves a heal action by ID
func (d *PgHealActionDAO) GetByID(ctx context.Context, id string) (*HealAction, error) {
	const q = `SELECT id, desc, type, rules FROM heal_actions WHERE id = $1`

	row := d.DB.QueryRowContext(ctx, q, id)
	var action HealAction
	var rulesJSON string

	err := row.Scan(&action.ID, &action.Desc, &action.Type, &rulesJSON)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("no heal action found with id: %s", id)
		}
		return nil, fmt.Errorf("failed to get heal action by id: %w", err)
	}

	action.Rules = json.RawMessage(rulesJSON)
	return &action, nil
}

// Create creates a new heal action
func (d *PgHealActionDAO) Create(ctx context.Context, action *HealAction) error {
	const q = `INSERT INTO heal_actions (id, desc, type, rules) VALUES ($1, $2, $3, $4)`

	_, err := d.DB.ExecContext(ctx, q, action.ID, action.Desc, action.Type, string(action.Rules))
	if err != nil {
		return fmt.Errorf("failed to create heal action: %w", err)
	}

	return nil
}

// Update updates an existing heal action
func (d *PgHealActionDAO) Update(ctx context.Context, action *HealAction) error {
	const q = `UPDATE heal_actions SET desc = $2, type = $3, rules = $4 WHERE id = $1`

	result, err := d.DB.ExecContext(ctx, q, action.ID, action.Desc, action.Type, string(action.Rules))
	if err != nil {
		return fmt.Errorf("failed to update heal action: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("no heal action found with id: %s", action.ID)
	}

	return nil
}

// Delete deletes a heal action by ID
func (d *PgHealActionDAO) Delete(ctx context.Context, id string) error {
	const q = `DELETE FROM heal_actions WHERE id = $1`

	result, err := d.DB.ExecContext(ctx, q, id)
	if err != nil {
		return fmt.Errorf("failed to delete heal action: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("no heal action found with id: %s", id)
	}

	return nil
}

// List retrieves all heal actions
func (d *PgHealActionDAO) List(ctx context.Context) ([]*HealAction, error) {
	const q = `SELECT id, desc, type, rules FROM heal_actions ORDER BY type, id`

	rows, err := d.DB.QueryContext(ctx, q)
	if err != nil {
		return nil, fmt.Errorf("failed to list heal actions: %w", err)
	}
	defer rows.Close()

	var actions []*HealAction
	for rows.Next() {
		var action HealAction
		var rulesJSON string

		err := rows.Scan(&action.ID, &action.Desc, &action.Type, &rulesJSON)
		if err != nil {
			return nil, fmt.Errorf("failed to scan heal action: %w", err)
		}

		action.Rules = json.RawMessage(rulesJSON)
		actions = append(actions, &action)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating heal actions: %w", err)
	}

	return actions, nil
}
