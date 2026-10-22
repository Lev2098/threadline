-- ============================================================================
-- Threadline comments: database schema for MySQL Workbench
--
-- How to open:  MySQL Workbench -> File -> Import -> Reverse Engineer MySQL
--               Create Script... -> select this file -> Execute -> Finish.
--               An EER diagram with both tables and their relations appears.
--
-- The application runs on PostgreSQL (see schema.postgresql.sql, generated
-- from the Django migration). This file is the same design in MySQL 8 dialect.
-- Differences, all because of MySQL limitations:
--   * PostgreSQL uses PARTIAL indexes (WHERE parent_id IS NULL) for the root
--     table; MySQL has none, so the root indexes below cover all rows.
--   * `path` is TEXT; MySQL needs a prefix length to index it.
--   * `ip` is INET in PostgreSQL, VARCHAR(39) here.
--   * ON DELETE CASCADE is shown to document intent; in the application,
--     cascades are done by Django's ORM, and PostgreSQL's FKs have no
--     DB-level cascade. (InnoDB would also stop cascading after 15 levels.)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS `threadline` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `threadline`;

-- ----------------------------------------------------------------------------
-- comments: every comment, root or reply.
--   parent_id     direct parent (NULL for root comments)
--   root_id       root of the thread (= id for roots), lets a whole thread be
--                 read with one range scan
--   path          materialized path of zero-padded ids, e.g.
--                 "0000000001.0000000005.0000000042"; ORDER BY path gives
--                 depth-first, chronological thread order
--   username, email, home_page   author data, denormalized for sorting
--   client_id, ip, user_agent    data identifying the client (anonymous JWT)
--   text_source   text as typed;  text_html  validated, sanitized XHTML
--   replies_count number of replies in the thread (kept on root rows)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `comments` (
  `id`            BIGINT        NOT NULL AUTO_INCREMENT,
  `parent_id`     BIGINT        NULL,
  `root_id`       BIGINT        NULL,
  `path`          TEXT          NOT NULL,
  `username`      VARCHAR(64)   NOT NULL,
  `email`         VARCHAR(254)  NOT NULL,
  `home_page`     VARCHAR(2048) NOT NULL DEFAULT '',
  `text_source`   TEXT          NOT NULL,
  `text_html`     TEXT          NOT NULL,
  `client_id`     VARCHAR(64)   NOT NULL,
  `ip`            VARCHAR(39)   NULL,
  `user_agent`    VARCHAR(512)  NOT NULL DEFAULT '',
  `replies_count` INT UNSIGNED  NOT NULL DEFAULT 0,
  `created_at`    DATETIME(6)   NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `comments_root_created_idx` (`parent_id`, `created_at` DESC, `id` DESC),
  INDEX `comments_root_username_idx` (`parent_id`, (LOWER(`username`)), `id`),
  INDEX `comments_root_email_idx` (`parent_id`, (LOWER(`email`)), `id`),
  INDEX `comments_thread_path_idx` (`root_id`, `path`(255)),
  INDEX `comments_parent_idx` (`parent_id`),
  INDEX `comments_client_id_idx` (`client_id`),
  CONSTRAINT `comments_parent_fk`
    FOREIGN KEY (`parent_id`) REFERENCES `comments` (`id`) ON DELETE CASCADE,
  CONSTRAINT `comments_root_fk`
    FOREIGN KEY (`root_id`) REFERENCES `comments` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB;

-- ----------------------------------------------------------------------------
-- comment_attachments: at most one file per comment (1:1).
--   kind     'image' (JPG/GIF/PNG, downscaled to fit 320x240) or 'text' (TXT <= 100 KB)
--   file     storage path under MEDIA_ROOT
--   width/height  final image size after downscaling (NULL for text)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `comment_attachments` (
  `id`            BIGINT            NOT NULL AUTO_INCREMENT,
  `comment_id`    BIGINT            NOT NULL,
  `kind`          VARCHAR(8)        NOT NULL,
  `file`          VARCHAR(255)      NOT NULL,
  `original_name` VARCHAR(255)      NOT NULL,
  `size`          INT UNSIGNED      NOT NULL,
  `width`         SMALLINT UNSIGNED NULL,
  `height`        SMALLINT UNSIGNED NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `comment_attachments_comment_id_uq` (`comment_id`),
  CONSTRAINT `comment_attachments_comment_fk`
    FOREIGN KEY (`comment_id`) REFERENCES `comments` (`id`) ON DELETE CASCADE,
  CONSTRAINT `comment_attachments_kind_chk` CHECK (`kind` IN ('image', 'text'))
) ENGINE = InnoDB;
