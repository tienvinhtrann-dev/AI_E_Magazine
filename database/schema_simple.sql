-- ============================================
-- SCHEMA ĐƠN GIẢN CHO TRANG BÁO ĐIỆN TỬ AI
-- ============================================

-- Tạo database nếu chưa tồn tại (KHÔNG xóa dữ liệu cũ)
CREATE DATABASE IF NOT EXISTS ai_e_magazine_v2 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE ai_e_magazine_v2;

-- ============================================
-- BẢNG USERS - Quản lý người dùng
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    full_name VARCHAR(255),
    auth_provider VARCHAR(20) DEFAULT 'local',
    google_id VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- BẢNG ARTICLES - Quản lý bài báo
-- ============================================
CREATE TABLE IF NOT EXISTS articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    keywords VARCHAR(500),
    topic VARCHAR(255),
    description TEXT,
    status ENUM('draft', 'published', 'pending') DEFAULT 'draft',
    source_urls TEXT COMMENT 'JSON array của các URL nguồn tham khảo',
    image_urls TEXT COMMENT 'JSON array của các URL hình ảnh từ bài gốc',
    view_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at TIMESTAMP NULL,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    FULLTEXT idx_search (title, content, keywords)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- BẢNG GENERATION_LOGS - Log quá trình tạo bài
-- ============================================
CREATE TABLE IF NOT EXISTS generation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    article_id INT,
    topic VARCHAR(255),
    keywords VARCHAR(500),
    sources_crawled INT DEFAULT 0,
    articles_found INT DEFAULT 0,
    generation_time FLOAT COMMENT 'Thời gian tạo (giây)',
    status ENUM('success', 'failed', 'processing') DEFAULT 'processing',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- BẢNG COMMENTS - Bình luận cho bài viết
-- ============================================
CREATE TABLE IF NOT EXISTS comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================
-- DỮ LIỆU MẪU
-- ============================================

-- Tạo admin mặc định (password: admin123) - chỉ insert nếu chưa tồn tại
INSERT IGNORE INTO users (email, password, role, full_name) VALUES
('admin@magazine.com', 'scrypt:32768:8:1$kGR7VpXgwHxdqF8R$5e6e8a9e1d8f3c4b2a1e7d9f6c3b8a4e5d2f1c9b7a6e4d3f2c1b8a7e5d4f3c2b1a9e8d7f6c5b4a3e2d1f9c8b7a6e5d4f3c2b1a', 'admin', 'Administrator'),
('user@magazine.com', 'scrypt:32768:8:1$kGR7VpXgwHxdqF8R$5e6e8a9e1d8f3c4b2a1e7d9f6c3b8a4e5d2f1c9b7a6e4d3f2c1b8a7e5d4f3c2b1a9e8d7f6c5b4a3e2d1f9c8b7a6e5d4f3c2b1a', 'user', 'Test User');

-- Tạo bài báo mẫu - chỉ insert nếu chưa tồn tại
INSERT IGNORE INTO articles (user_id, title, content, summary, keywords, topic, status, published_at) VALUES
(2, 'Trí Tuệ Nhân Tạo Đang Thay Đổi Thế Giới', 
'Trí tuệ nhân tạo (AI) đang trở thành một trong những công nghệ quan trọng nhất của thế kỷ 21. Từ nhận dạng giọng nói đến xe tự lái, AI đang thay đổi cách chúng ta sống và làm việc.\n\nCác ứng dụng của AI ngày càng phổ biến trong nhiều lĩnh vực như y tế, giáo dục, tài chính và sản xuất. Các công ty công nghệ lớn như Google, Microsoft và OpenAI đang đầu tư mạnh mẽ vào nghiên cứu AI.\n\nTuy nhiên, sự phát triển của AI cũng đặt ra nhiều thách thức về đạo đức, quyền riêng tư và việc làm. Chúng ta cần có những quy định phù hợp để đảm bảo AI phát triển theo hướng có lợi cho nhân loại.',
'AI đang thay đổi thế giới với các ứng dụng trong nhiều lĩnh vực, nhưng cũng đặt ra nhiều thách thức.',
'trí tuệ nhân tạo, AI, công nghệ, machine learning',
'Công nghệ',
'published',
NOW());

-- ============================================
-- THÔNG TIN DATABASE
-- ============================================
SELECT 
    'Database created successfully!' as message,
    COUNT(*) as total_users 
FROM users;

SELECT 
    'Sample data inserted!' as message,
    COUNT(*) as total_articles 
FROM articles;
