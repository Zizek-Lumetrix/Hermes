ALTER TABLE conclusions ADD COLUMN IF NOT EXISTS merged_from TEXT[];
ALTER TABLE conclusions ADD COLUMN IF NOT EXISTS merged_into TEXT;
