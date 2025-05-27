-- MySQLShell dump 2.0.1  Distrib Ver 9.3.0 for Linux on x86_64 - for MySQL 9.3.0 (MySQL Community Server (GPL)), for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: airportdb    Table: airport_reachable
-- ------------------------------------------------------
-- Server version	9.3.0

--
-- Current Database: `airportdb`
--

USE `airportdb`;

--
-- Table structure for table `airport_reachable`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `airport_reachable` (
  `airport_id` smallint NOT NULL COMMENT 'Identifier for the airport.',
  `hops` int DEFAULT NULL COMMENT 'Number of intermediate flights (or legs) needed to reach this airport from a central location or hub.',
  PRIMARY KEY (`airport_id`),
  CONSTRAINT `airport_reachable_ibfk_1` FOREIGN KEY (`airport_id`) REFERENCES `airport` (`airport_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Flughafen DB by Stefan Pröll, Eva Zangerle, Wolfgang Gassler is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0' SECONDARY_ENGINE=RAPID;
/*!40101 SET character_set_client = @saved_cs_client */;
