-- MySQLShell dump 2.0.1  Distrib Ver 9.3.0 for Linux on x86_64 - for MySQL 9.3.0 (MySQL Community Server (GPL)), for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: airportdb    Table: airplane_type
-- ------------------------------------------------------
-- Server version	9.3.0

--
-- Current Database: `airportdb`
--

USE `airportdb`;

--
-- Table structure for table `airplane_type`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `airplane_type` (
  `type_id` int NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for each airplane type or model.',
  `identifier` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Model identifier or code for the airplane type.',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT 'Additional details or specifications about the airplane type.',
  PRIMARY KEY (`type_id`),
  FULLTEXT KEY `description_full` (`identifier`,`description`)
) ENGINE=InnoDB AUTO_INCREMENT=343 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Flughafen DB by Stefan Pröll, Eva Zangerle, Wolfgang Gassler is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0' SECONDARY_ENGINE=RAPID;
/*!40101 SET character_set_client = @saved_cs_client */;
