-- 数据库初始化脚本
-- 对应 models.py 的最新结构

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `phone` varchar(20) NOT NULL,
  `nickname` varchar(50) DEFAULT NULL,
  `license` varchar(255) DEFAULT NULL,
  `cash` bigint(20) DEFAULT 0,
  `bank` bigint(20) DEFAULT 0,
  `crypto` bigint(20) DEFAULT 0,
  `citizenid` varchar(50) DEFAULT NULL,
  `charinfo` json DEFAULT NULL,
  `is_bound` tinyint(1) DEFAULT 0,
  `is_admin` tinyint(1) DEFAULT 0,
  `is_super_admin` tinyint(1) DEFAULT 0,
  `admin_permissions` json DEFAULT NULL,
  `status` varchar(20) DEFAULT 'active',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_phone` (`phone`),
  UNIQUE KEY `ix_users_citizenid` (`citizenid`),
  KEY `ix_users_license` (`license`),
  KEY `ix_users_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for items
-- ----------------------------
DROP TABLE IF EXISTS `items`;
CREATE TABLE `items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `price` int(11) DEFAULT 0,
  `label` varchar(100) DEFAULT NULL,
  `type` varchar(20) DEFAULT '消耗品',
  `image_url` varchar(255) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_items_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for user_vehicles
-- ----------------------------
DROP TABLE IF EXISTS `user_vehicles`;
CREATE TABLE `user_vehicles` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `plate` varchar(10) NOT NULL,
  `model_name` varchar(50) NOT NULL,
  `type` varchar(20) DEFAULT '轿车',
  `image_url` varchar(255) DEFAULT NULL,
  `state` int(11) DEFAULT 100,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_vehicles_plate` (`plate`),
  KEY `ix_user_vehicles_id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `user_vehicles_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for user_inventory
-- ----------------------------
DROP TABLE IF EXISTS `user_inventory`;
CREATE TABLE `user_inventory` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `item_id` int(11) NOT NULL,
  `slot` int(11) DEFAULT 1,
  `count` int(11) DEFAULT 1,
  `info` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_user_inventory_id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `item_id` (`item_id`),
  CONSTRAINT `user_inventory_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `user_inventory_ibfk_2` FOREIGN KEY (`item_id`) REFERENCES `items` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for banners
-- ----------------------------
DROP TABLE IF EXISTS `banners`;
CREATE TABLE `banners` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(100) DEFAULT NULL,
  `desc` varchar(255) DEFAULT NULL,
  `image_url` varchar(255) NOT NULL,
  `link_url` varchar(255) DEFAULT NULL,
  `sort_order` int(11) DEFAULT 0,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_banners_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- Table structure for announcements
-- ----------------------------
DROP TABLE IF EXISTS `announcements`;
CREATE TABLE `announcements` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `content` varchar(255) DEFAULT NULL,
  `enabled` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_announcements_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for products
-- ----------------------------
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `price` int(11) DEFAULT 0,
  `original_price` int(11) DEFAULT 0,
  `vehicle_model` varchar(50) DEFAULT NULL,
  `garage` varchar(50) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `image_url` varchar(255) DEFAULT NULL,
  `stock` int(11) DEFAULT 0,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_products_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for subscription_plans
-- ----------------------------
DROP TABLE IF EXISTS `subscription_plans`;
CREATE TABLE `subscription_plans` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `price` int(11) DEFAULT 0,
  `duration` int(11) DEFAULT 30,
  `description` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_subscription_plans_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for user_subscriptions
-- ----------------------------
DROP TABLE IF EXISTS `user_subscriptions`;
CREATE TABLE `user_subscriptions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `plan_id` int(11) NOT NULL,
  `start_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `end_date` datetime NOT NULL,
  `status` varchar(20) DEFAULT 'active',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_user_subscriptions_id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `plan_id` (`plan_id`),
  CONSTRAINT `user_subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `user_subscriptions_ibfk_2` FOREIGN KEY (`plan_id`) REFERENCES `subscription_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for tickets
-- ----------------------------
DROP TABLE IF EXISTS `tickets`;
CREATE TABLE `tickets` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `title` varchar(100) NOT NULL,
  `type` varchar(20) DEFAULT 'bug',
  `status` varchar(20) DEFAULT 'open',
  `content` varchar(2000) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_tickets_id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `tickets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for ticket_messages
-- ----------------------------
DROP TABLE IF EXISTS `ticket_messages`;
CREATE TABLE `ticket_messages` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `ticket_id` bigint(20) NOT NULL,
  `sender_role` varchar(20) NOT NULL,
  `content` varchar(2000) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_ticket_messages_id` (`id`),
  KEY `ticket_id` (`ticket_id`),
  CONSTRAINT `ticket_messages_ibfk_1` FOREIGN KEY (`ticket_id`) REFERENCES `tickets` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for orders
-- ----------------------------
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
  `id` varchar(50) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `type` varchar(20) DEFAULT 'product',
  `total_amount` int(11) DEFAULT 0,
  `status` varchar(20) DEFAULT 'completed',
  `is_delivered` tinyint(1) DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for order_items
-- ----------------------------
DROP TABLE IF EXISTS `order_items`;
CREATE TABLE `order_items` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `order_id` varchar(50) NOT NULL,
  `product_id` int(11) DEFAULT NULL,
  `plan_id` int(11) DEFAULT NULL,
  `item_name` varchar(100) DEFAULT NULL,
  `price` int(11) DEFAULT 0,
  `quantity` int(11) DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `ix_order_items_id` (`id`),
  KEY `order_id` (`order_id`),
  KEY `product_id` (`product_id`),
  KEY `plan_id` (`plan_id`),
  CONSTRAINT `order_items_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `order_items_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  CONSTRAINT `order_items_ibfk_3` FOREIGN KEY (`plan_id`) REFERENCES `subscription_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
