-- 一次性修补：迁移降级半途失败（非事务 DDL）遗留的现场
-- 将 schema 手工恢复到 i9a0b1c2d3e4 完整状态（与迁移 upgrade 产物等价）
ALTER TABLE question_review_record
  ADD COLUMN batch_id BIGINT NULL COMMENT '手动批量审核批次 ID（生成任务自动审核为空）';
ALTER TABLE question_review_record
  ADD CONSTRAINT fk_qrr_batch FOREIGN KEY (batch_id)
    REFERENCES question_review_batch (id) ON DELETE SET NULL;
CREATE INDEX idx_qrr_batch_id ON question_review_record (batch_id);
CREATE INDEX idx_qrr_trigger_source ON question_review_record (trigger_source);
CREATE INDEX idx_qrb_created_at ON question_review_batch (created_at);

CREATE TABLE question_review_batch_item (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '批次项 ID',
  batch_id BIGINT NOT NULL COMMENT '所属批次 ID',
  question_id BIGINT NOT NULL COMMENT '题目 ID',
  status VARCHAR(20) NOT NULL COMMENT '处理状态: queued/running/completed/failed/skipped',
  claim_key VARCHAR(32) NULL COMMENT '活动认领键：排队/执行期间为 active，终态后 NULL',
  skip_reason VARCHAR(50) NULL COMMENT '跳过原因',
  review_record_id BIGINT NULL COMMENT '对应 question_review_record.id',
  error_code VARCHAR(50) NULL COMMENT '单题错误码',
  error_message TEXT NULL COMMENT '单题失败原因',
  started_at DATETIME NULL COMMENT '开始时间',
  finished_at DATETIME NULL COMMENT '完成时间',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_qrbi_batch_question (batch_id, question_id),
  UNIQUE KEY uq_qrbi_question_claim (question_id, claim_key),
  KEY idx_qrbi_batch_id (batch_id),
  KEY idx_qrbi_question_id (question_id),
  CONSTRAINT fk_qrbi_batch FOREIGN KEY (batch_id)
    REFERENCES question_review_batch (id) ON DELETE CASCADE,
  CONSTRAINT fk_qrbi_question FOREIGN KEY (question_id)
    REFERENCES question (id) ON DELETE RESTRICT,
  CONSTRAINT fk_qrbi_record FOREIGN KEY (review_record_id)
    REFERENCES question_review_record (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
