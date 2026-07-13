ALTER TABLE analysis_review_queue
  ADD COLUMN reviewed_by VARCHAR(128) NULL AFTER status,
  ADD COLUMN review_note TEXT NULL AFTER reviewed_by,
  ADD COLUMN reviewed_at DATETIME NULL AFTER review_note;
