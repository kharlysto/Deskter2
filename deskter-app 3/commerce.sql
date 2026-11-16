CREATE TABLE IF NOT EXISTS course_modules(
 id INTEGER PRIMARY KEY,listing_id INTEGER NOT NULL REFERENCES listings(id),
 title TEXT NOT NULL,position INTEGER NOT NULL CHECK(position>=0),created INTEGER NOT NULL,
 UNIQUE(listing_id,position));
CREATE TABLE IF NOT EXISTS course_lessons(
 id INTEGER PRIMARY KEY,module_id INTEGER NOT NULL REFERENCES course_modules(id),
 title TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('text','video')),
 body TEXT NOT NULL DEFAULT '',video_url TEXT NOT NULL DEFAULT '',
 position INTEGER NOT NULL CHECK(position>=0),created INTEGER NOT NULL,
 UNIQUE(module_id,position));
CREATE TABLE IF NOT EXISTS lesson_progress(
 buyer INTEGER NOT NULL REFERENCES users(id),lesson_id INTEGER NOT NULL REFERENCES course_lessons(id),
 completed_at INTEGER NOT NULL,PRIMARY KEY(buyer,lesson_id));
CREATE TABLE IF NOT EXISTS reviews(
 id INTEGER PRIMARY KEY,listing_id INTEGER NOT NULL REFERENCES listings(id),
 buyer INTEGER NOT NULL REFERENCES users(id),rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
 body TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,
 UNIQUE(listing_id,buyer));
CREATE INDEX IF NOT EXISTS course_modules_listing ON course_modules(listing_id,position);
CREATE INDEX IF NOT EXISTS course_lessons_module ON course_lessons(module_id,position);
CREATE INDEX IF NOT EXISTS lesson_progress_buyer ON lesson_progress(buyer,lesson_id);
CREATE INDEX IF NOT EXISTS reviews_listing ON reviews(listing_id,created);
CREATE INDEX IF NOT EXISTS orders_paid_listing ON orders(kind,status,target_id,paid_at);
