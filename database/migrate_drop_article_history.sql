-- ============================================================
-- Migration: Xóa bảng article_history (không dùng trong dự án)
-- Chạy 1 lần trong phpMyAdmin hoặc MySQL CLI
-- ============================================================

USE ai_e_magazine_v2;

-- Bảng article_history chỉ được ghi vào (INSERT), không có
-- trang nào đọc/hiển thị dữ liệu nên không cần thiết.
DROP TABLE IF EXISTS article_history;
