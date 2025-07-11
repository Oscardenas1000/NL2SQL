-- MySQL dump 10.13  Distrib 9.3.0, for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: Coffee_Shop
-- ------------------------------------------------------
-- Server version	9.3.2-cloud

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup 
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '11e45044-b254-452a-8f81-8befac5920cd:1-26,
50db9527-1ec4-11f0-ad7c-02001700f0e6:1-261231';

--
-- Current Database: `Coffee_Shop`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `Coffee_Shop` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `Coffee_Shop`;

--
-- Table structure for table `products`
--

DROP TABLE IF EXISTS `products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products` (
  `product_id` int NOT NULL COMMENT 'Primary key: uniquely identifies a product',
  `name` varchar(100) NOT NULL COMMENT 'Product name (e.g., Espresso, Muffin)',
  `unit_price` decimal(8,2) NOT NULL COMMENT 'Unit price in USD',
  PRIMARY KEY (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products`
--

LOCK TABLES `products` WRITE;
/*!40000 ALTER TABLE `products` DISABLE KEYS */;
INSERT INTO `products` VALUES (1,'Espresso',2.50),(2,'Americano',2.75),(3,'Latte',4.00),(4,'Cappuccino',3.75),(5,'Mocha',4.50),(6,'Flat White',4.25),(7,'Macchiato',3.00),(8,'Cortado',3.25),(9,'Cold Brew',3.50),(10,'Iced Coffee',3.00),(11,'Iced Latte',4.25),(12,'Iced Mocha',4.75),(13,'Frappuccino',5.00),(14,'Chai Latte',3.75),(15,'Matcha Latte',4.50),(16,'Hot Chocolate',3.50),(17,'Tea (Black)',2.00),(18,'Tea (Green)',2.25),(19,'Herbal Tea',2.50),(20,'Bottled Water',1.50),(21,'Sparkling Water',2.00),(22,'Orange Juice',3.00),(23,'Apple Juice',3.00),(24,'Lemonade',2.75),(25,'Iced Tea',2.75),(26,'Croissant',2.75),(27,'Blueberry Muffin',2.50),(28,'Chocolate Muffin',2.75),(29,'Scone',2.50),(30,'Bagel',1.75),(31,'Bagel with Cream Cheese',3.00),(32,'Banana Bread',2.75),(33,'Chocolate Chip Cookie',1.50),(34,'Oatmeal Cookie',1.50),(35,'Brownie',2.50),(36,'Cheesecake Slice',4.50),(37,'Carrot Cake Slice',4.00),(38,'Quiche Lorraine',5.00),(39,'Spinach & Feta Quiche',5.00),(40,'Caesar Salad',6.50),(41,'Greek Salad',6.75),(42,'Garden Salad',6.00),(43,'Chicken Salad',7.50),(44,'Tuna Salad',7.00),(45,'Avocado Toast',5.50),(46,'Turkey Sandwich',6.50),(47,'Ham & Cheese Sandwich',6.00),(48,'Veggie Wrap',6.25),(49,'Protein Box',8.00),(50,'Yogurt Parfait',4.00);
/*!40000 ALTER TABLE `products` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sales`
--

DROP TABLE IF EXISTS `sales`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sales` (
  `sale_id` int NOT NULL COMMENT 'Primary key: uniquely identifies each sale PO',
  `sale_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of sale (YYYY-MM-DD HH:MM:SS)',
  `items` json NOT NULL COMMENT 'JSON array of items: [{"name":X,"quantity":Y}, …] Product names and individual prices are listed within "products" table',
  `total_amount` decimal(10,2) NOT NULL COMMENT 'Total amount for the entire sale in USD',
  PRIMARY KEY (`sale_id`),
  CONSTRAINT `sales_chk_1` CHECK (json_valid(`items`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sales`
--

LOCK TABLES `sales` WRITE;
/*!40000 ALTER TABLE `sales` DISABLE KEYS */;
INSERT INTO `sales` VALUES (1,'2025-04-08 21:56:30','[{\"name\": \"Chai Latte\", \"quantity\": 1}, {\"name\": \"Veggie Wrap\", \"quantity\": 3}]',22.50),(2,'2025-01-30 09:02:04','[{\"name\": \"Cortado\", \"quantity\": 2}, {\"name\": \"Espresso\", \"quantity\": 2}]',11.50),(3,'2025-01-08 02:08:55','[{\"name\": \"Yogurt Parfait\", \"quantity\": 3}, {\"name\": \"Oatmeal Cookie\", \"quantity\": 1}]',13.50),(4,'2025-04-20 03:48:05','[{\"name\": \"Caesar Salad\", \"quantity\": 3}]',19.50),(5,'2025-06-15 21:18:48','[{\"name\": \"Flat White\", \"quantity\": 2}, {\"name\": \"Espresso\", \"quantity\": 2}, {\"name\": \"Apple Juice\", \"quantity\": 2}, {\"name\": \"Carrot Cake Slice\", \"quantity\": 2}]',27.50),(6,'2025-07-02 05:26:25','[{\"name\": \"Iced Latte\", \"quantity\": 1}, {\"name\": \"Orange Juice\", \"quantity\": 3}, {\"name\": \"Espresso\", \"quantity\": 1}]',15.75),(7,'2025-03-01 17:53:45','[{\"name\": \"Cold Brew\", \"quantity\": 3}, {\"name\": \"Quiche Lorraine\", \"quantity\": 1}]',15.50),(8,'2025-07-01 20:30:25','[{\"name\": \"Matcha Latte\", \"quantity\": 2}, {\"name\": \"Protein Box\", \"quantity\": 3}]',33.00),(9,'2025-06-06 02:30:56','[{\"name\": \"Brownie\", \"quantity\": 1}]',2.50),(10,'2025-04-22 02:44:01','[{\"name\": \"Caesar Salad\", \"quantity\": 1}, {\"name\": \"Turkey Sandwich\", \"quantity\": 3}, {\"name\": \"Chocolate Muffin\", \"quantity\": 3}]',34.25),(11,'2025-06-14 07:09:50','[{\"name\": \"Spinach & Feta Quiche\", \"quantity\": 3}]',15.00),(12,'2025-02-16 14:49:08','[{\"name\": \"Sparkling Water\", \"quantity\": 3}]',6.00),(13,'2025-06-26 22:39:18','[{\"name\": \"Hot Chocolate\", \"quantity\": 1}]',3.50),(14,'2025-03-24 17:26:09','[{\"name\": \"Tea (Black)\", \"quantity\": 2}]',4.00),(15,'2025-05-28 11:32:03','[{\"name\": \"Cappuccino\", \"quantity\": 1}, {\"name\": \"Cortado\", \"quantity\": 2}]',10.25),(16,'2025-01-31 00:49:55','[{\"name\": \"Frappuccino\", \"quantity\": 1}, {\"name\": \"Espresso\", \"quantity\": 1}, {\"name\": \"Carrot Cake Slice\", \"quantity\": 1}, {\"name\": \"Lemonade\", \"quantity\": 2}]',17.00),(17,'2025-01-14 00:16:06','[{\"name\": \"Iced Coffee\", \"quantity\": 2}, {\"name\": \"Spinach & Feta Quiche\", \"quantity\": 2}, {\"name\": \"Veggie Wrap\", \"quantity\": 3}]',34.75),(18,'2025-05-13 19:15:05','[{\"name\": \"Flat White\", \"quantity\": 2}, {\"name\": \"Brownie\", \"quantity\": 2}, {\"name\": \"Greek Salad\", \"quantity\": 2}]',27.00),(19,'2025-07-07 12:48:18','[{\"name\": \"Greek Salad\", \"quantity\": 3}]',20.25),(20,'2025-01-01 19:40:34','[{\"name\": \"Iced Mocha\", \"quantity\": 2}, {\"name\": \"Tea (Green)\", \"quantity\": 2}, {\"name\": \"Chocolate Chip Cookie\", \"quantity\": 3}]',18.50),(21,'2025-04-26 04:16:22','[{\"name\": \"Cheesecake Slice\", \"quantity\": 2}]',9.00),(22,'2025-04-02 12:09:35','[{\"name\": \"Matcha Latte\", \"quantity\": 2}, {\"name\": \"Tuna Salad\", \"quantity\": 2}, {\"name\": \"Iced Tea\", \"quantity\": 3}, {\"name\": \"Bagel with Cream Cheese\", \"quantity\": 3}]',40.25),(23,'2025-01-27 02:08:32','[{\"name\": \"Chocolate Muffin\", \"quantity\": 2}, {\"name\": \"Iced Tea\", \"quantity\": 3}, {\"name\": \"Flat White\", \"quantity\": 2}]',22.25),(24,'2025-04-20 10:38:47','[{\"name\": \"Protein Box\", \"quantity\": 1}, {\"name\": \"Mocha\", \"quantity\": 2}, {\"name\": \"Herbal Tea\", \"quantity\": 2}]',22.00),(25,'2025-05-24 22:14:48','[{\"name\": \"Hot Chocolate\", \"quantity\": 1}, {\"name\": \"Sparkling Water\", \"quantity\": 3}, {\"name\": \"Caesar Salad\", \"quantity\": 2}, {\"name\": \"Caesar Salad\", \"quantity\": 1}]',29.00),(26,'2025-07-03 23:31:16','[{\"name\": \"Blueberry Muffin\", \"quantity\": 2}]',5.00),(27,'2025-04-23 10:57:01','[{\"name\": \"Brownie\", \"quantity\": 1}, {\"name\": \"Spinach & Feta Quiche\", \"quantity\": 3}, {\"name\": \"Bottled Water\", \"quantity\": 2}]',20.50),(28,'2025-04-10 20:44:48','[{\"name\": \"Cold Brew\", \"quantity\": 3}, {\"name\": \"Latte\", \"quantity\": 1}, {\"name\": \"Cortado\", \"quantity\": 2}, {\"name\": \"Lemonade\", \"quantity\": 1}]',23.75),(29,'2025-05-18 13:41:22','[{\"name\": \"Hot Chocolate\", \"quantity\": 2}, {\"name\": \"Americano\", \"quantity\": 2}]',12.50),(30,'2025-04-11 09:01:44','[{\"name\": \"Cappuccino\", \"quantity\": 3}, {\"name\": \"Carrot Cake Slice\", \"quantity\": 1}, {\"name\": \"Tea (Black)\", \"quantity\": 2}]',19.25),(31,'2025-06-13 15:33:44','[{\"name\": \"Brownie\", \"quantity\": 1}, {\"name\": \"Lemonade\", \"quantity\": 1}, {\"name\": \"Iced Mocha\", \"quantity\": 2}, {\"name\": \"Bagel\", \"quantity\": 3}]',20.00),(32,'2025-01-05 02:12:46','[{\"name\": \"Croissant\", \"quantity\": 3}]',8.25),(33,'2025-06-15 15:53:57','[{\"name\": \"Mocha\", \"quantity\": 1}]',4.50),(34,'2025-03-07 00:34:52','[{\"name\": \"Blueberry Muffin\", \"quantity\": 1}]',2.50),(35,'2025-03-14 14:49:54','[{\"name\": \"Quiche Lorraine\", \"quantity\": 3}, {\"name\": \"Blueberry Muffin\", \"quantity\": 1}]',17.50),(36,'2025-01-13 04:22:56','[{\"name\": \"Yogurt Parfait\", \"quantity\": 1}, {\"name\": \"Herbal Tea\", \"quantity\": 1}, {\"name\": \"Ham & Cheese Sandwich\", \"quantity\": 2}, {\"name\": \"Spinach & Feta Quiche\", \"quantity\": 2}]',28.50),(37,'2025-03-19 19:59:45','[{\"name\": \"Brownie\", \"quantity\": 2}, {\"name\": \"Flat White\", \"quantity\": 1}, {\"name\": \"Iced Latte\", \"quantity\": 1}]',13.50),(38,'2025-03-08 13:01:08','[{\"name\": \"Matcha Latte\", \"quantity\": 2}, {\"name\": \"Chocolate Chip Cookie\", \"quantity\": 1}]',10.50),(39,'2025-05-10 07:06:37','[{\"name\": \"Cold Brew\", \"quantity\": 3}, {\"name\": \"Apple Juice\", \"quantity\": 1}]',13.50),(40,'2025-01-01 09:13:54','[{\"name\": \"Orange Juice\", \"quantity\": 1}, {\"name\": \"Iced Coffee\", \"quantity\": 3}, {\"name\": \"Cappuccino\", \"quantity\": 2}, {\"name\": \"Mocha\", \"quantity\": 1}]',24.00),(41,'2025-07-02 09:01:05','[{\"name\": \"Sparkling Water\", \"quantity\": 1}, {\"name\": \"Orange Juice\", \"quantity\": 1}]',5.00),(42,'2025-04-24 23:08:09','[{\"name\": \"Bagel with Cream Cheese\", \"quantity\": 3}, {\"name\": \"Ham & Cheese Sandwich\", \"quantity\": 3}, {\"name\": \"Tuna Salad\", \"quantity\": 3}]',48.00),(43,'2025-06-23 06:48:16','[{\"name\": \"Mocha\", \"quantity\": 2}, {\"name\": \"Yogurt Parfait\", \"quantity\": 2}, {\"name\": \"Herbal Tea\", \"quantity\": 2}, {\"name\": \"Espresso\", \"quantity\": 3}]',29.50),(44,'2025-04-13 20:13:00','[{\"name\": \"Tuna Salad\", \"quantity\": 1}]',7.00),(45,'2025-03-24 17:38:55','[{\"name\": \"Sparkling Water\", \"quantity\": 2}, {\"name\": \"Quiche Lorraine\", \"quantity\": 2}, {\"name\": \"Oatmeal Cookie\", \"quantity\": 3}]',18.50),(46,'2025-04-19 22:51:49','[{\"name\": \"Iced Tea\", \"quantity\": 2}, {\"name\": \"Americano\", \"quantity\": 2}]',11.00),(47,'2025-01-11 23:01:58','[{\"name\": \"Tuna Salad\", \"quantity\": 3}, {\"name\": \"Frappuccino\", \"quantity\": 1}]',26.00),(48,'2025-05-12 01:54:11','[{\"name\": \"Tea (Green)\", \"quantity\": 3}, {\"name\": \"Bottled Water\", \"quantity\": 2}, {\"name\": \"Avocado Toast\", \"quantity\": 2}, {\"name\": \"Iced Latte\", \"quantity\": 2}]',29.25),(49,'2025-04-08 20:04:18','[{\"name\": \"Tuna Salad\", \"quantity\": 3}]',21.00),(50,'2025-03-17 04:51:48','[{\"name\": \"Hot Chocolate\", \"quantity\": 1}, {\"name\": \"Mocha\", \"quantity\": 3}]',17.00),(51,'2025-04-13 08:15:14','[{\"name\": \"Yogurt Parfait\", \"quantity\": 2}, {\"name\": \"Mocha\", \"quantity\": 3}, {\"name\": \"Herbal Tea\", \"quantity\": 2}]',26.50),(52,'2025-02-04 15:52:51','[{\"name\": \"Chai Latte\", \"quantity\": 2}, {\"name\": \"Mocha\", \"quantity\": 3}, {\"name\": \"Iced Mocha\", \"quantity\": 1}, {\"name\": \"Caesar Salad\", \"quantity\": 1}]',32.25),(53,'2025-01-16 00:58:57','[{\"name\": \"Veggie Wrap\", \"quantity\": 1}, {\"name\": \"Flat White\", \"quantity\": 3}]',19.00),(54,'2025-04-26 04:54:39','[{\"name\": \"Protein Box\", \"quantity\": 3}]',24.00),(55,'2025-06-06 08:35:44','[{\"name\": \"Hot Chocolate\", \"quantity\": 2}, {\"name\": \"Americano\", \"quantity\": 2}]',12.50),(56,'2025-01-30 02:32:18','[{\"name\": \"Chai Latte\", \"quantity\": 2}]',7.50),(57,'2025-04-12 17:43:12','[{\"name\": \"Turkey Sandwich\", \"quantity\": 3}, {\"name\": \"Croissant\", \"quantity\": 2}, {\"name\": \"Herbal Tea\", \"quantity\": 1}]',27.50),(58,'2025-06-28 15:40:36','[{\"name\": \"Lemonade\", \"quantity\": 2}, {\"name\": \"Spinach & Feta Quiche\", \"quantity\": 3}, {\"name\": \"Flat White\", \"quantity\": 2}]',29.00),(59,'2025-06-01 08:25:17','[{\"name\": \"Veggie Wrap\", \"quantity\": 1}, {\"name\": \"Blueberry Muffin\", \"quantity\": 2}, {\"name\": \"Chocolate Muffin\", \"quantity\": 2}, {\"name\": \"Greek Salad\", \"quantity\": 2}]',30.25),(60,'2025-02-05 01:38:19','[{\"name\": \"Espresso\", \"quantity\": 1}, {\"name\": \"Blueberry Muffin\", \"quantity\": 2}, {\"name\": \"Cold Brew\", \"quantity\": 2}, {\"name\": \"Cappuccino\", \"quantity\": 2}]',22.00),(61,'2025-03-12 07:01:52','[{\"name\": \"Apple Juice\", \"quantity\": 2}]',6.00),(62,'2025-01-26 04:53:52','[{\"name\": \"Cortado\", \"quantity\": 1}, {\"name\": \"Americano\", \"quantity\": 1}, {\"name\": \"Garden Salad\", \"quantity\": 2}, {\"name\": \"Scone\", \"quantity\": 2}]',23.00),(63,'2025-06-07 15:43:18','[{\"name\": \"Banana Bread\", \"quantity\": 3}, {\"name\": \"Tea (Green)\", \"quantity\": 3}, {\"name\": \"Lemonade\", \"quantity\": 3}, {\"name\": \"Carrot Cake Slice\", \"quantity\": 2}]',31.25),(64,'2025-05-03 01:58:50','[{\"name\": \"Sparkling Water\", \"quantity\": 3}, {\"name\": \"Americano\", \"quantity\": 1}, {\"name\": \"Cappuccino\", \"quantity\": 3}]',20.00),(65,'2025-05-21 10:19:44','[{\"name\": \"Blueberry Muffin\", \"quantity\": 2}, {\"name\": \"Cortado\", \"quantity\": 2}]',11.50),(66,'2025-03-05 02:56:01','[{\"name\": \"Chocolate Chip Cookie\", \"quantity\": 3}]',4.50),(67,'2025-01-07 03:39:23','[{\"name\": \"Americano\", \"quantity\": 3}]',8.25),(68,'2025-02-04 17:39:59','[{\"name\": \"Garden Salad\", \"quantity\": 3}, {\"name\": \"Chai Latte\", \"quantity\": 3}, {\"name\": \"Tea (Green)\", \"quantity\": 3}]',36.00),(69,'2025-03-06 16:17:33','[{\"name\": \"Cheesecake Slice\", \"quantity\": 3}, {\"name\": \"Greek Salad\", \"quantity\": 1}, {\"name\": \"Cold Brew\", \"quantity\": 2}, {\"name\": \"Iced Mocha\", \"quantity\": 2}]',36.75),(70,'2025-01-26 15:25:31','[{\"name\": \"Cortado\", \"quantity\": 3}, {\"name\": \"Latte\", \"quantity\": 1}, {\"name\": \"Cold Brew\", \"quantity\": 1}]',17.25),(71,'2025-06-01 12:05:09','[{\"name\": \"Sparkling Water\", \"quantity\": 1}, {\"name\": \"Herbal Tea\", \"quantity\": 2}, {\"name\": \"Chocolate Muffin\", \"quantity\": 2}, {\"name\": \"Ham & Cheese Sandwich\", \"quantity\": 3}]',30.50),(72,'2025-01-13 07:54:18','[{\"name\": \"Tea (Green)\", \"quantity\": 1}, {\"name\": \"Sparkling Water\", \"quantity\": 3}, {\"name\": \"Cold Brew\", \"quantity\": 3}, {\"name\": \"Avocado Toast\", \"quantity\": 1}]',24.25),(73,'2025-05-31 12:59:54','[{\"name\": \"Tea (Black)\", \"quantity\": 1}, {\"name\": \"Ham & Cheese Sandwich\", \"quantity\": 1}]',8.00),(74,'2025-03-23 18:56:53','[{\"name\": \"Quiche Lorraine\", \"quantity\": 1}, {\"name\": \"Americano\", \"quantity\": 2}]',10.50),(75,'2025-05-28 17:12:29','[{\"name\": \"Tea (Black)\", \"quantity\": 1}]',2.00),(76,'2025-01-23 14:39:49','[{\"name\": \"Macchiato\", \"quantity\": 1}, {\"name\": \"Hot Chocolate\", \"quantity\": 3}]',13.50),(77,'2025-03-21 06:06:29','[{\"name\": \"Chocolate Muffin\", \"quantity\": 1}]',2.75),(78,'2025-01-26 21:26:32','[{\"name\": \"Chai Latte\", \"quantity\": 1}]',3.75),(79,'2025-04-30 10:08:21','[{\"name\": \"Chocolate Muffin\", \"quantity\": 3}, {\"name\": \"Brownie\", \"quantity\": 2}, {\"name\": \"Iced Mocha\", \"quantity\": 2}, {\"name\": \"Latte\", \"quantity\": 2}]',30.75),(80,'2025-04-10 22:20:47','[{\"name\": \"Cortado\", \"quantity\": 1}, {\"name\": \"Iced Tea\", \"quantity\": 3}]',11.50),(81,'2025-06-28 23:24:42','[{\"name\": \"Matcha Latte\", \"quantity\": 3}, {\"name\": \"Oatmeal Cookie\", \"quantity\": 2}, {\"name\": \"Chocolate Muffin\", \"quantity\": 1}]',19.25),(82,'2025-03-06 16:25:58','[{\"name\": \"Bagel\", \"quantity\": 3}, {\"name\": \"Bottled Water\", \"quantity\": 1}, {\"name\": \"Herbal Tea\", \"quantity\": 1}, {\"name\": \"Bagel with Cream Cheese\", \"quantity\": 1}]',12.25),(83,'2025-03-02 16:41:44','[{\"name\": \"Bottled Water\", \"quantity\": 2}]',3.00),(84,'2025-02-25 20:14:04','[{\"name\": \"Orange Juice\", \"quantity\": 2}, {\"name\": \"Greek Salad\", \"quantity\": 1}]',12.75),(85,'2025-04-02 13:03:34','[{\"name\": \"Macchiato\", \"quantity\": 2}, {\"name\": \"Bagel\", \"quantity\": 1}]',7.75),(86,'2025-06-13 04:17:13','[{\"name\": \"Chai Latte\", \"quantity\": 3}]',11.25),(87,'2025-06-01 16:08:28','[{\"name\": \"Garden Salad\", \"quantity\": 2}]',12.00),(88,'2025-03-13 03:38:42','[{\"name\": \"Tea (Green)\", \"quantity\": 3}, {\"name\": \"Scone\", \"quantity\": 3}, {\"name\": \"Cappuccino\", \"quantity\": 2}]',21.75),(89,'2025-03-11 20:40:31','[{\"name\": \"Iced Coffee\", \"quantity\": 1}]',3.00),(90,'2025-03-25 22:26:50','[{\"name\": \"Espresso\", \"quantity\": 1}, {\"name\": \"Iced Coffee\", \"quantity\": 1}, {\"name\": \"Espresso\", \"quantity\": 1}, {\"name\": \"Latte\", \"quantity\": 1}]',12.00),(91,'2025-04-21 20:58:34','[{\"name\": \"Iced Latte\", \"quantity\": 1}, {\"name\": \"Chai Latte\", \"quantity\": 2}, {\"name\": \"Tea (Black)\", \"quantity\": 3}]',17.75),(92,'2025-03-31 09:51:29','[{\"name\": \"Matcha Latte\", \"quantity\": 3}, {\"name\": \"Greek Salad\", \"quantity\": 3}, {\"name\": \"Cold Brew\", \"quantity\": 1}, {\"name\": \"Frappuccino\", \"quantity\": 2}]',47.25),(93,'2025-02-19 01:39:54','[{\"name\": \"Latte\", \"quantity\": 2}, {\"name\": \"Iced Latte\", \"quantity\": 2}, {\"name\": \"Scone\", \"quantity\": 3}]',24.00),(94,'2025-06-08 07:45:22','[{\"name\": \"Cappuccino\", \"quantity\": 2}]',7.50),(95,'2025-03-29 15:06:01','[{\"name\": \"Quiche Lorraine\", \"quantity\": 3}, {\"name\": \"Chicken Salad\", \"quantity\": 2}]',30.00),(96,'2025-03-18 08:29:20','[{\"name\": \"Mocha\", \"quantity\": 3}, {\"name\": \"Chai Latte\", \"quantity\": 1}, {\"name\": \"Chocolate Muffin\", \"quantity\": 3}, {\"name\": \"Tea (Green)\", \"quantity\": 3}]',32.25),(97,'2025-06-01 19:54:22','[{\"name\": \"Iced Tea\", \"quantity\": 3}]',8.25),(98,'2025-04-18 04:38:41','[{\"name\": \"Carrot Cake Slice\", \"quantity\": 3}, {\"name\": \"Flat White\", \"quantity\": 2}]',20.50),(99,'2025-04-01 07:39:43','[{\"name\": \"Protein Box\", \"quantity\": 2}, {\"name\": \"Iced Tea\", \"quantity\": 1}, {\"name\": \"Blueberry Muffin\", \"quantity\": 1}, {\"name\": \"Chicken Salad\", \"quantity\": 2}]',36.25),(100,'2025-02-06 09:36:47','[{\"name\": \"Orange Juice\", \"quantity\": 2}, {\"name\": \"Turkey Sandwich\", \"quantity\": 1}]',12.50);
/*!40000 ALTER TABLE `sales` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'Coffee_Shop'
--

--
-- Dumping routines for database 'Coffee_Shop'
--
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-07-11 18:40:48
