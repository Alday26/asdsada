/*
SQLyog Ultimate v10.00 Beta1
MySQL - 5.5.5-10.4.32-MariaDB : Database - ecoms3rddb
*********************************************************************
*/

/*!40101 SET NAMES utf8 */;

/*!40101 SET SQL_MODE=''*/;

/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/`ecoms3rddb` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;

USE `ecoms3rddb`;

/*Table structure for table `cart` */

DROP TABLE IF EXISTS `cart`;

CREATE TABLE `cart` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `variant_id` int(11) NOT NULL,
  `quantity` int(11) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_cart_item` (`user_id`,`product_id`,`variant_id`),
  KEY `product_id` (`product_id`),
  KEY `variant_id` (`variant_id`),
  CONSTRAINT `cart_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `cart_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  CONSTRAINT `cart_ibfk_3` FOREIGN KEY (`variant_id`) REFERENCES `product_variants` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=96 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `cart` */

insert  into `cart`(`id`,`user_id`,`product_id`,`variant_id`,`quantity`,`created_at`) values (81,24,37,42,1,'2026-05-07 16:00:58');

/*Table structure for table `messages` */

DROP TABLE IF EXISTS `messages`;

CREATE TABLE `messages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` int(11) NOT NULL,
  `sender_id` int(11) NOT NULL,
  `receiver_id` int(11) NOT NULL,
  `message` text NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`),
  KEY `sender_id` (`sender_id`),
  KEY `receiver_id` (`receiver_id`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `messages_ibfk_2` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `messages_ibfk_3` FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `messages` */

/*Table structure for table `notifications` */

DROP TABLE IF EXISTS `notifications`;

CREATE TABLE `notifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `variant_id` int(11) DEFAULT NULL,
  `message` varchar(255) NOT NULL,
  `is_read` tinyint(1) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `notifications` */

/*Table structure for table `orders` */

DROP TABLE IF EXISTS `orders`;

CREATE TABLE `orders` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `buyer_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `variant_id` int(11) NOT NULL,
  `image_url` varchar(255) DEFAULT NULL,
  `quantity` int(11) NOT NULL,
  `total_price` decimal(10,2) NOT NULL,
  `status` enum('pending','shipped','delivered','cancelled','approved','declined','completed') DEFAULT 'pending',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `payment_method` varchar(50) NOT NULL DEFAULT 'Cash on Hand',
  `buyer_notified` tinyint(1) DEFAULT 0,
  `seller_notified` tinyint(1) DEFAULT 0,
  `report_status` enum('none','reported','redelivering') DEFAULT 'none',
  `rider_id` int(11) DEFAULT NULL,
  `delivery_status` enum('pending','ready_for_delivery','out_for_delivery','delivered','returned_to_seller') DEFAULT 'pending',
  `delivered_at` datetime DEFAULT NULL,
  `latitude` decimal(10,6) DEFAULT NULL,
  `longitude` decimal(10,6) DEFAULT NULL,
  `address` text DEFAULT NULL,
  `shipping_fee` decimal(10,2) DEFAULT 0.00,
  `proof_image` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `buyer_id` (`buyer_id`),
  KEY `product_id` (`product_id`),
  KEY `variant_id` (`variant_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`buyer_id`) REFERENCES `users` (`id`),
  CONSTRAINT `orders_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  CONSTRAINT `orders_ibfk_3` FOREIGN KEY (`variant_id`) REFERENCES `product_variants` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `orders` */

insert  into `orders`(`id`,`buyer_id`,`product_id`,`variant_id`,`image_url`,`quantity`,`total_price`,`status`,`created_at`,`payment_method`,`buyer_notified`,`seller_notified`,`report_status`,`rider_id`,`delivery_status`,`delivered_at`,`latitude`,`longitude`,`address`,`shipping_fee`,`proof_image`) values (55,25,61,66,NULL,1,'0.00','declined','2026-05-12 16:06:54','Cash on Delivery',1,0,'none',NULL,'pending',NULL,'14.074100','121.329800','Unknown address','0.00',NULL),(56,25,61,66,NULL,1,'0.00','declined','2026-05-12 16:12:40','Cash on Delivery',1,0,'none',NULL,'pending',NULL,'9.232249','124.059195','Unknown address','0.00',NULL),(57,25,60,65,'0f2fc60b7de74df0b48cd6753bb7dbba',1,'0.00','declined','2026-05-13 11:48:13','Cash on Delivery',1,0,'none',NULL,'pending',NULL,'14.012694','121.345381','Unknown address','0.00',NULL),(58,25,58,63,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg',1,'0.00','declined','2026-05-13 13:59:33','cod',1,0,'none',NULL,'pending',NULL,'14.599500','120.984200','Unknown address','0.00',NULL),(59,25,58,63,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg',1,'0.00','declined','2026-05-13 14:05:31','cod',1,0,'none',NULL,'pending',NULL,'14.599500','120.984200','Unknown address','0.00',NULL),(60,25,58,63,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg',1,'0.00','declined','2026-05-13 14:08:06','cod',1,0,'none',NULL,'pending',NULL,'14.596457','120.981522','Unknown address','0.00',NULL),(61,25,58,63,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg',1,'0.00','declined','2026-05-13 14:15:00','cod',1,0,'none',NULL,'pending',NULL,'14.597546','120.984761','Unknown address','0.00',NULL),(62,25,58,63,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg',1,'0.00','declined','2026-05-13 14:15:20','cod',1,0,'none',NULL,'pending',NULL,'14.599500','120.984200','Unknown address','0.00',NULL),(63,25,58,63,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg',1,'0.00','declined','2026-05-13 14:21:52','cod',1,0,'none',NULL,'pending',NULL,'14.596829','120.981429','Unknown address','50.00',NULL),(64,25,59,64,'/static/images/8c1cbf5e5dec472aab0c3f52d3d0c118',1,'0.00','declined','2026-05-13 14:29:44','cod',1,0,'none',NULL,'pending',NULL,'14.598475','120.980590','Unknown address','50.00',NULL),(65,25,61,66,'/static/images/d7690d62ffb7487eb83ac10205f25815',1,'0.00','declined','2026-05-13 14:30:02','cod',1,0,'none',NULL,'pending',NULL,'14.598154','120.987654','Unknown address','50.00',NULL),(66,25,61,66,'/static/images/d7690d62ffb7487eb83ac10205f25815',1,'0.00','declined','2026-05-16 19:40:59','cod',1,0,'none',NULL,'pending',NULL,'14.581897','120.972914','Unknown address','50.00',NULL),(67,25,61,66,'/static/images/d7690d62ffb7487eb83ac10205f25815',1,'0.00','','2026-05-21 13:42:17','cod',1,0,'none',26,'delivered','2026-05-21 14:45:18','14.597754','120.983788','Unknown address','50.00',NULL),(68,25,61,66,'/static/images/d7690d62ffb7487eb83ac10205f25815',1,'0.00','','2026-05-21 13:47:53','cod',1,0,'none',26,'delivered','2026-05-21 14:41:37','14.591240','120.974310','Unknown address','50.00',NULL),(69,25,61,66,'/static/images/d7690d62ffb7487eb83ac10205f25815',1,'0.00','','2026-05-21 14:55:44','cod',1,0,'none',26,'delivered','2026-05-21 17:03:20','14.596527','120.981248','Unknown address','50.00','/static/proof_deliveries/scaled_d7676a0f-28aa-44d2-8b0a-b2f19cd0c7a02509260205150987750.jpg'),(70,25,60,65,'0f2fc60b7de74df0b48cd6753bb7dbba',1,'0.00','','2026-05-21 15:36:10','Cash on Delivery',1,0,'none',35,'out_for_delivery',NULL,'14.177900','121.233600','Unknown address','0.00',NULL),(71,25,60,65,'/static/images/0f2fc60b7de74df0b48cd6753bb7dbba',1,'0.00','pending','2026-05-21 17:32:07','cod',0,0,'none',NULL,'pending',NULL,'14.599500','120.984200','Unknown address','50.00',NULL),(72,25,42,47,'/static/images/db76bb6d762a43dc9662e533dd8e3d8f',1,'0.00','','2026-05-21 17:34:21','cod',1,0,'none',26,'delivered','2026-05-21 17:35:19','14.599500','120.984200','Unknown address','50.00','/static/proof_deliveries/scaled_406de476-8639-4c56-aa22-2e41577eff5a2607089325794765660.jpg');

/*Table structure for table `product_likes` */

DROP TABLE IF EXISTS `product_likes`;

CREATE TABLE `product_likes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`product_id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `product_likes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `product_likes_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `product_likes` */

/*Table structure for table `product_variants` */

DROP TABLE IF EXISTS `product_variants`;

CREATE TABLE `product_variants` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` int(11) NOT NULL,
  `color` varchar(50) NOT NULL,
  `stock` int(11) DEFAULT 0,
  `image_url` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `product_variants_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=78 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `product_variants` */

insert  into `product_variants`(`id`,`product_id`,`color`,`stock`,`image_url`) values (42,37,'Brown',254,'/static/images/38ad1882243b4fcc9e23f658a1218b1b'),(43,38,'White',2112,'/static/images/4f8906f147fe466180d7f723bdf33c50'),(44,39,'White',65,'/static/images/1ac046b1b43a43a192ad9e1bc7cb7f33'),(45,40,'Black',875,'/static/images/13532b9ac53148edbba9164170051e24'),(46,41,'Blue',87,'/static/images/7d70b20ade684d00a11c64d3e41e498a'),(47,42,'Titanium',18,'/static/images/db76bb6d762a43dc9662e533dd8e3d8f'),(48,43,'Black',123,'/static/images/0284edeb636c4d998e0f57da06383701'),(49,44,'Black',23,'/static/images/36f27793cbb94633b3fef934fb2a8f91'),(50,45,'Black',244,'/static/images/280635c2feb04e9cae5c1e9f22b2a197'),(51,46,'White',765,'/static/images/afa2b880cc094b6abd1f4619c3c8f0ef'),(52,47,'White',43,'/static/images/9c040c8066c24fc583c5e13508f29139.6 Full HD Laptop'),(53,48,'White',432,'/static/images/65a3e5995ff64c1db22a6e8fbc6b5f94.8'),(54,49,'White',76,'/static/images/57b5ffa20f1548b29e0465add3da0205'),(55,50,'Black',67,'/static/images/15281723cabd47baa7c0fcaf0a750194.6 FHD Gaming Laptop'),(56,51,'Silver',45,'/static/images/31c642ffa0d8454787bc4a0a49b954db.6 FHD Portable Monitor'),(57,52,'Pink',35,'/static/images/a8e7a00d18aa41ce818241482bb6af33'),(58,53,'Black',87,'/static/images/228ec313fb6945269219a4af6abe97df'),(59,54,'Black',123,'/static/images/72e2ec9104124a7ab54ede19300b5c05'),(60,55,'Black',87,'/static/images/f71dd4d756084c9eac41069bff9e5cc3'),(61,56,'Black',87,'/static/images/75335db0efcd4ba5849b855a6da8ff26.1 Soundbar with Subwoofer (HW-B550)'),(62,57,'White',45,'/static/images/1ef3ac44c4cc458187b245c9dd8e6dc3'),(63,58,'Black',90,'/static/images/9397c74f3c1a4f008e8c2e59083e5240.jpg'),(64,59,'Silver',78,'/static/images/8c1cbf5e5dec472aab0c3f52d3d0c118'),(65,60,'Black',43,'/static/images/0f2fc60b7de74df0b48cd6753bb7dbba'),(66,61,'White',31,'/static/images/d7690d62ffb7487eb83ac10205f25815'),(67,62,'Black',12,'/static/images/58077892de0c4a0ea24a01c266e48c6a.jpg'),(68,63,'Black',63,'/static/images/b46ffd6febfe48d8b90aac016aae9c47.jpg'),(69,64,'Green',45,'/static/images/4f352814db5043e1af9c3c18233d8ad5.jpg'),(70,65,'Black',222,'/static/images/82d6374053a84234bc7660e242a947f2.jpg'),(71,65,'Orange',222,'/static/images/4868fa7c10524c7cb26b8a5193bc7d03.jpg'),(72,66,'White',2222,'/static/images/97d0a6ff36544637b6054ea806119f77'),(73,67,'White',2222,'/static/images/eae2d415e1524368b017cee77d0656a7.jpg'),(74,68,'Black',2222,'/static/images/b0f94b5fa67b44c0a96632bc9b0c1bcb.jpg'),(75,69,'White',22,'/static/images/bd6a739e9d044669af8bcd2ccee1af42.png'),(76,70,'Orange',22,'/static/images/46595129199e431cb2319b2b1e8cd0c1.jpg'),(77,71,'Pink',222,'/static/images/c7237fc212694c0b98b77e86228267b5.jpg');

/*Table structure for table `products` */

DROP TABLE IF EXISTS `products`;

CREATE TABLE `products` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `name` varchar(150) NOT NULL,
  `description` text DEFAULT NULL,
  `price` decimal(10,2) NOT NULL,
  `stock` int(11) NOT NULL DEFAULT 0,
  `image_url` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `category` varchar(100) DEFAULT NULL,
  `is_deleted` tinyint(1) DEFAULT 0,
  `total_purchases` int(11) DEFAULT 0,
  `is_featured` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `products_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=72 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `products` */

insert  into `products`(`id`,`user_id`,`name`,`description`,`price`,`stock`,`image_url`,`created_at`,`category`,`is_deleted`,`total_purchases`,`is_featured`) values (37,24,'Smartphone (T95 Smart Watch Style)','Smartphones are all-in-one devices for calls, social media, gaming, and photos. Modern ones also support AI features and high-quality cameras.','2019.00',0,'/static/images/someimage.jpg','2026-05-07 15:59:53','Electronics and Gadgets',1,0,0),(38,24,'Smartwatch','Smartwatches can track fitness, show notifications, and sometimes even connect calls and apps from your phone.','1485.00',0,NULL,'2026-05-07 16:05:50','Electronics and Gadgets',0,0,0),(39,24,'Power Bank','Power banks let you charge your phone anywhere—super useful when traveling or during emergencies.','648.98',0,NULL,'2026-05-07 16:06:51','Electronics and Gadgets',0,0,0),(40,24,'Bluetooth Speaker','Bluetooth speakers give loud, clear music anywhere—perfect for parties, gaming, or outdoor use.','9499.00',0,NULL,'2026-05-07 16:07:21','Electronics and Gadgets',0,0,0),(41,24,'Wireless Earbuds','Earbuds are small wireless audio devices perfect for music, gaming, and calls without messy wires.','878.21',0,NULL,'2026-05-07 16:08:03','Electronics and Gadgets',0,0,0),(42,27,'Phone','jsjddb','12.00',0,NULL,'2026-05-07 17:14:44','Mobile Phones & Accessories',0,1,0),(43,27,'Spigen Tough Armor MagFit Case','A rugged dual-layer protective case constructed from a flexible TPU body and a hard polycarbonate back. ','1450.00',0,NULL,'2026-05-07 17:17:38','Mobile Phones & Accessories',0,0,0),(44,27,'Anker 30W USB-C GaN Fast Charger (Nano 3)','An ultra-compact wall charger utilizing advanced Gallium Nitride (GaN) technology to deliver 30W of high-speed charging power in a body roughly the size of a golf ball.','1290.00',0,NULL,'2026-05-07 17:18:27','Mobile Phones & Accessories',0,0,0),(45,27,'UGREEN USB-C to USB-C Cable (100W, Braided)','A durable 6.6-foot (2-meter) USB-C to USB-C charging and data sync cable wrapped in a double-braided nylon exterior for enhanced durability and tangle resistance.','720.00',0,NULL,'2026-05-07 17:19:09','Mobile Phones & Accessories',0,0,0),(46,27,'Apple AirPods Pro (2nd Gen) with MagSafe Case','Apple\'s premium true wireless earbuds featuring active noise cancellation (ANC), adaptive transparency mode, and personalized spatial audio for an immersive listening experience.','14990.00',0,NULL,'2026-05-07 17:19:51','Mobile Phones & Accessories',0,0,0),(47,28,'Acer Aspire 5 15.6\" Full HD Laptop','A versatile 15.6-inch laptop designed for everyday productivity and entertainment.','27990.00',0,NULL,'2026-05-07 17:22:05','Laptops, Desktops & Monitors',0,0,0),(48,28,'HP Pavilion All-in-One Desktop 23.8\"','A sleek all-in-one desktop that combines the computer and a 23.8-inch Full HD touchscreen display into a single, space-saving unit.','38990.00',0,NULL,'2026-05-07 17:22:44','Laptops, Desktops & Monitors',0,0,0),(49,28,'Samsung 24\" IPS FHD Monitor (LS24R350)','A 24-inch Full HD (1920x1080) monitor with an IPS panel that delivers vivid colors and wide 178-degree viewing angles.','6989.99',0,NULL,'2026-05-07 17:23:17','Laptops, Desktops & Monitors',0,0,0),(50,28,'Lenovo LOQ 15.6\" FHD Gaming Laptop','A powerful entry-level gaming laptop built for high-performance gaming and demanding tasks. Equipped with an Intel Core i5 13th Gen processor and an NVIDIA GeForce RTX 4050 GPU, it can run the latest AAA games smoothly.','54990.00',0,NULL,'2026-05-07 17:23:52','Laptops, Desktops & Monitors',0,0,0),(51,28,'Arzopa 15.6\" FHD Portable Monitor','An ultra-slim second screen for users who need extra display space while traveling. ','4550.00',0,NULL,'2026-05-07 17:24:38','Laptops, Desktops & Monitors',0,0,0),(52,31,'JBL Flip 6 Portable Bluetooth Speaker','A compact and rugged portable Bluetooth speaker that delivers surprisingly powerful sound for its size.','5299.00',0,NULL,'2026-05-07 17:27:03','Audio & Video Equipment',0,0,0),(53,31,'Sony WH-1000XM5 Wireless Noise-Cancelling Headphones','Sony\'s premium over-ear wireless headphones set a benchmark in noise cancellation with eight microphones and an advanced auto-optimizer that adjusts to your environment. \r\n\r\n','19990.00',0,NULL,'2026-05-07 17:27:46','Audio & Video Equipment',0,0,0),(54,31,'Logitech C920 HD Pro Webcam','A reliable and popular 1080p Full HD webcam ideal for professional video calls, livestreaming, and content creation.','3950.00',0,NULL,'2026-05-07 17:28:32','Audio & Video Equipment',0,0,0),(55,31,'Audio-Technica AT2020 Cardioid Condenser Microphone','A legendary entry-level studio condenser microphone known for its durability, wide dynamic range, and exceptionally low self-noise.','6750.00',0,NULL,'2026-05-07 17:29:07','Audio & Video Equipment',0,0,0),(56,31,'Samsung B-Series 2.1 Soundbar with Subwoofer (HW-B550)','An easy-to-set-up 2.1 channel soundbar system that instantly upgrades your TV\'s audio experience.','8989.99',0,NULL,'2026-05-07 17:29:52','Audio & Video Equipment',0,0,0),(57,29,'ASUS ROG Zephyrus G14','A powerful yet portable 14-inch gaming laptop designed for high-performance gaming and content creation.','69995.00',0,NULL,'2026-05-07 17:35:17','Laptops, Desktops & Monitors',0,0,0),(58,29,'Lenovo ThinkPad X1 Carbon Gen 11','A premium enterprise-class laptop built for maximum productivity and durability.','89990.00',0,NULL,'2026-05-07 17:36:00','Laptops, Desktops & Monitors',0,0,0),(59,29,'Apple Mac Mini (M4, 2024)','An incredibly compact desktop computer that delivers outstanding performance through Apple\'s M4 chip.','36990.00',0,NULL,'2026-05-07 17:36:45','Laptops, Desktops & Monitors',0,0,0),(60,29,'Gigabyte M27Q KVM Gaming Monitor','A 27-inch QHD (2560x1440) gaming monitor with an IPS panel and a blazing-fast 170Hz refresh rate for ultra-smooth motion.','15949.98',0,NULL,'2026-05-07 17:37:35','Laptops, Desktops & Monitors',0,1,0),(61,29,'CalDigit TS4 Thunderbolt 4 Dock','A high-performance universal docking station that turns a laptop into a full desktop workstation with a single Thunderbolt 4 cable.','21950.00',0,NULL,'2026-05-07 17:38:19','Laptops, Desktops & Monitors',0,3,0),(62,27,'test','test','12.00',0,NULL,'2026-05-12 23:41:54','Mobile Phones & Accessories',1,0,0),(63,27,'Phone test','test','23.00',0,NULL,'2026-05-12 23:46:02','Mobile Phones & Accessories',1,0,0),(64,27,'Test','test','43.00',0,NULL,'2026-05-12 23:56:03','Mobile Phones & Accessories',1,0,0),(65,27,'adawd','dawda','222.00',0,NULL,'2026-05-12 23:59:26','Mobile Phones & Accessories',1,0,0),(66,27,'Galaxy S24 Ultra','awdad','222.00',0,NULL,'2026-05-13 00:18:25','Mobile Phones & Accessories',1,0,0),(67,27,'hi lance','dawdawd','2222.00',0,NULL,'2026-05-13 00:19:31','Mobile Phones & Accessories',1,0,0),(68,29,'dadaw','dadwdwa','222.00',0,NULL,'2026-05-13 00:39:11','Laptops, Desktops & Monitors',1,0,0),(69,29,'daddaw','dwaad','22.00',0,NULL,'2026-05-13 00:43:39','Laptops, Desktops & Monitors',1,0,0),(70,29,'aw','dwaawd','222.00',0,NULL,'2026-05-13 00:45:51','Laptops, Desktops & Monitors',1,0,0),(71,29,'Phone','22','2222.00',0,NULL,'2026-05-13 00:46:51','Laptops, Desktops & Monitors',1,0,0);

/*Table structure for table `reports` */

DROP TABLE IF EXISTS `reports`;

CREATE TABLE `reports` (
  `report_id` int(11) NOT NULL AUTO_INCREMENT,
  `order_id` int(11) NOT NULL,
  `buyer_id` int(11) NOT NULL,
  `seller_id` int(11) NOT NULL,
  `reason` text NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`report_id`),
  KEY `order_id` (`order_id`),
  KEY `buyer_id` (`buyer_id`),
  KEY `seller_id` (`seller_id`),
  CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `reports_ibfk_2` FOREIGN KEY (`buyer_id`) REFERENCES `users` (`id`),
  CONSTRAINT `reports_ibfk_3` FOREIGN KEY (`seller_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `reports` */

/*Table structure for table `reviews` */

DROP TABLE IF EXISTS `reviews`;

CREATE TABLE `reviews` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `order_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `buyer_id` int(11) NOT NULL,
  `rating` int(11) NOT NULL CHECK (`rating` between 1 and 5),
  `comment` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_review` (`order_id`,`buyer_id`),
  KEY `product_id` (`product_id`),
  KEY `buyer_id` (`buyer_id`),
  CONSTRAINT `reviews_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reviews_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reviews_ibfk_3` FOREIGN KEY (`buyer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `reviews` */

/*Table structure for table `rider_applications` */

DROP TABLE IF EXISTS `rider_applications`;

CREATE TABLE `rider_applications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `license_file` varchar(255) NOT NULL,
  `station` enum('Sta Cruz','Pagsanjan','Siniloan','Lumban','Sambat') NOT NULL,
  `status` enum('Pending','Approved','Declined') DEFAULT 'Pending',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `rider_applications` */

/*Table structure for table `seller_applications` */

DROP TABLE IF EXISTS `seller_applications`;

CREATE TABLE `seller_applications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `email` varchar(150) DEFAULT NULL,
  `address` text DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `store_name` varchar(100) DEFAULT NULL,
  `product_genre` varchar(100) DEFAULT NULL,
  `status` enum('pending','approved','rejected') DEFAULT 'pending',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `seller_applications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `seller_applications` */

/*Table structure for table `users` */

DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lastname` varchar(100) NOT NULL,
  `firstname` varchar(100) NOT NULL,
  `middlename` varchar(100) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `email` varchar(150) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `category` enum('user','seller','rider') NOT NULL DEFAULT 'user',
  `seller_category` varchar(100) DEFAULT NULL,
  `profile_picture` varchar(255) DEFAULT NULL,
  `address` text DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `is_seller` tinyint(4) DEFAULT 0,
  `role` enum('user','admin','rider') DEFAULT 'user',
  `profile_image` varchar(255) DEFAULT NULL,
  `region` varchar(100) DEFAULT NULL,
  `province` varchar(100) DEFAULT NULL,
  `municipality` varchar(100) DEFAULT NULL,
  `barangay` varchar(100) DEFAULT NULL,
  `street_name` varchar(255) DEFAULT NULL,
  `house_number` varchar(50) DEFAULT NULL,
  `valid_id` varchar(255) DEFAULT NULL,
  `business_permit` varchar(255) DEFAULT NULL,
  `driver_license` varchar(255) DEFAULT NULL,
  `motor_registration` varchar(255) DEFAULT NULL,
  `ocr_image` varchar(255) DEFAULT NULL,
  `is_approved` tinyint(1) NOT NULL DEFAULT 0,
  `store_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `users` */

insert  into `users`(`id`,`lastname`,`firstname`,`middlename`,`username`,`password`,`email`,`phone_number`,`category`,`seller_category`,`profile_picture`,`address`,`phone`,`is_seller`,`role`,`profile_image`,`region`,`province`,`municipality`,`barangay`,`street_name`,`house_number`,`valid_id`,`business_permit`,`driver_license`,`motor_registration`,`ocr_image`,`is_approved`,`store_name`) values (23,'','','','admin','admin123','admin@gmail.com',NULL,'user',NULL,NULL,NULL,NULL,0,'admin',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL),(24,'Delgado','Allyn Jade','L','allyn jade.delgado','Allyn123','delgadoallyn773@gmail.com','09262401080','user','Electronics and Gadgets','a4fb1df7c276436ebe91e66b86470b9b.png',NULL,NULL,1,'user',NULL,'040000000','043400000','043426000','Bagumbayan','Sitio Gumamela','342','059e8aa0587b40c0aac703a91f62e132.png','e9de2bf1bcc5434b92327527755fb2c3.png',NULL,NULL,NULL,1,'Allynsu'),(25,'Castillo','Andrew','A','andrew.castillo','Andrew123','andrewgwapo13@gmail.com','09262401080','user','','c312e97e62ee4a44936e0c45195c8369.png',NULL,NULL,0,'user',NULL,'040000000','043400000','043426000','Calios','Sitio Gumamela','342','44e175eb17e7440cb640562dfea40e81.png',NULL,NULL,NULL,NULL,1,''),(26,'Bonsol','Keziah','A','keziah.bonsol','Keziah123','keziahbonsol19@gmail.com','09262401080','user','','c13a36b223a04b04b241f27aede32384.png',NULL,NULL,0,'rider',NULL,'040000000','043400000','043415000','Bungkol','Sitio Gumamela','342',NULL,NULL,'ad22c69308bd41deb9a6cd8efc88fa84.png','f6581e51f5cd4950978f3de0a614c2ea.png','61e4aa10240b45bd9117dc7152ed2522.png',1,''),(27,'Alday','Lance Jethro','M','lance jethro.alday','Voidzz123','lancejethroemmanuel26@gmail.com','09262401080','user','Mobile Phones & Accessories','profile.jpg',NULL,NULL,1,'user',NULL,'040000000','043400000','043426000','San Juan','Sitio Gumamela','342','26eb7d26dcee4b43a12aaa61e0143a72.png','0922ba2f48f6444abbd712ab7d93e374.png',NULL,NULL,NULL,1,'Void Touch'),(28,'Veluz','Richard','R','richard.veluz','Chardi123','veluz.richard@gmail.com','09262401080','user','Laptops, Desktops & Monitors','d0757cd6c0cf4d7c8d7a09ad858b248a.png',NULL,NULL,1,'user',NULL,'040000000','043400000','043402000','Calo','Sitio Gumamela','342','0cc512844ce54049a2c564f34c1631e1.png','a2f3259a93cf4994a2aea7c13970df2e.png',NULL,NULL,NULL,1,'SeiShiro'),(29,'Lao','Jamelle','C','jamelle.lao','Woee123','Lordseven24@gmail.com','09262401080','user','Laptops, Desktops & Monitors','d3264659f81544bea87433e2da6d7c0d.png',NULL,NULL,1,'user',NULL,'040000000','043400000','043419000','Biñan','Sitio Gumamela','342','749fc390418d4400a12ba25bf2ff6ee6.png','f77fae251da74754bdd996fc969e321f.png',NULL,NULL,NULL,1,'Woe'),(30,'Jiclao','Jic','J','jic.jiclao','Woe1234','jiclao24@gmail.com','09262401080','user','','f07e858ae67a48e0803192406e339996.png',NULL,NULL,0,'user',NULL,'040000000','043400000','043419000','Biñan','Sitio Gumamela','342','25d6e9104d534efb87ab1f7ab375e1c8.png',NULL,NULL,NULL,NULL,1,''),(31,'Talisic','Precious','P','precious.talisic','Shannize123','precioustrishannt@gmail.com','09262401080','user','Audio & Video Equipment','ad78c0c692884f4f9a43567f18cdc371.png',NULL,NULL,1,'user',NULL,'040000000','045600000','045627000','Tapucan','Sitio Gumamela','342','c61af4805a534a768b9955b1c22fa894.png','c3db1d405180453ea42d98c057cc2b2d.png',NULL,NULL,NULL,1,'Shannize'),(32,'Voidzz','Voidzz','V','voidzz.voidzz','Asid123','asidstrike101@gmail.com','09262401080','user','','c747f79bf9b6447dbd9cd1d8be3464fc.png',NULL,NULL,0,'user',NULL,'040000000','043400000','043426000','San Pablo Sur','Sitio Gumamela','342','08c0a4dfa77d45f8a9666fff819e455a.png',NULL,NULL,NULL,NULL,1,''),(33,'Alday','Zeke','T','zeke.alday','Zeke123','zekeee1826@gmail.com','09262401080','user','','dbe718d2171246e5a60022f2b102bb8b.png',NULL,NULL,0,'user',NULL,'040000000','043400000','043426000','San Pablo Sur','Sitio Gumamela','342','7217563643134ddea0e1148541e56401.png',NULL,NULL,NULL,NULL,1,''),(34,'Edits','Voidzz','E','voidzz.edits','Edits123','voidzzedits1@gmail.com','09262401080','user','','4018c891e32b44a49854bb7e104b77b7.png',NULL,NULL,0,'user',NULL,'040000000','043400000','043426000','San Pablo Sur','Sitio Gumamela','342','42562a6a70c74ed4a59f722ed45879e7.png',NULL,NULL,NULL,NULL,1,''),(35,'Delgado','Allynsu','L','allynsu.delgado','Allynsu123','delgadoallyn772@gmail.com','09262401080','user','',NULL,NULL,NULL,0,'rider',NULL,'040000000','043400000','043426000','Bagumbayan','Sitio Gumamela','342',NULL,NULL,'5eaf2450118c42f79a949fd750e59ae4.png','5ce94063f79641fa82b763e5703c9661.png','143ee989985c49b2987fde76b78fd72b.png',1,''),(36,'Su','Yakiro','L','yakiro.su','Su123','yakirosu@gmail.com',NULL,'user','',NULL,NULL,NULL,0,'user',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,'');

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
