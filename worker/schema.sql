-- One row per listener per lesson per platform per day. No names, no IP addresses:
-- `visitor` is a one-way hash that changes every day, so it only tells "the same listener
-- today", never who they are. `hits` is how many requests that listener made (seeking, resuming).
CREATE TABLE IF NOT EXISTS plays (
  day      TEXT    NOT NULL,   -- YYYY-MM-DD, Israel time
  lesson   TEXT    NOT NULL,   -- lesson id, as in the catalog and the site
  platform TEXT    NOT NULL,
  visitor  TEXT    NOT NULL,
  hits     INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (day, lesson, platform, visitor)
);
CREATE INDEX IF NOT EXISTS plays_lesson ON plays (lesson, day);
