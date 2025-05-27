-- MySQLShell dump 2.0.1  Distrib Ver 9.3.0 for Linux on x86_64 - for MySQL 9.3.0 (MySQL Community Server (GPL)), for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: airportdb    Table: airplane
-- ------------------------------------------------------
-- Server version	9.3.0

--
-- Current Database: `airportdb`
--

USE `airportdb`;

--
-- Table structure for table `airplane`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `airplane` (
  `airplane_id` int NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for each airplane. This is the primary key and is auto-incremented.',
  `capacity` mediumint unsigned NOT NULL COMMENT 'Maximum number of passengers that the airplane can accommodate.',
  `type_id` int NOT NULL COMMENT 'Identifier for the airplane model/type. This is a foreign key referencing the airplane_type table.',
  `airline_id` int NOT NULL COMMENT 'Identifier of the airline that owns or operates the airplane. This is a foreign key referencing the airline table.',
  PRIMARY KEY (`airplane_id`),
  KEY `type_id` (`type_id`),
  CONSTRAINT `airplane_ibfk_1` FOREIGN KEY (`type_id`) REFERENCES `airplane_type` (`type_id`)
) ENGINE=InnoDB AUTO_INCREMENT=5584 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Flughafen DB by Stefan Pröll, Eva Zangerle, Wolfgang Gassler is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0' SECONDARY_ENGINE=RAPID;
/*!40101 SET character_set_client = @saved_cs_client */;
