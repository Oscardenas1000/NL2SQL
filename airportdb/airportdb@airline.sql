-- MySQLShell dump 2.0.1  Distrib Ver 9.3.0 for Linux on x86_64 - for MySQL 9.3.0 (MySQL Community Server (GPL)), for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: airportdb    Table: airline
-- ------------------------------------------------------
-- Server version	9.3.0

--
-- Current Database: `airportdb`
--

USE `airportdb`;

--
-- Table structure for table `airline`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `airline` (
  `airline_id` smallint NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for each airline.',
  `iata` char(2) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Two-character IATA code assigned to the airline, used globally for identification.',
  `airlinename` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'The full name of the airline.',
  `base_airport` smallint DEFAULT NULL COMMENT 'ID of the base airport for the airline, referring to the primary operational hub.',
  PRIMARY KEY (`airline_id`),
  UNIQUE KEY `iata_unq` (`iata`),
  KEY `base_airport_idx` (`base_airport`),
  CONSTRAINT `airline_ibfk_1` FOREIGN KEY (`base_airport`) REFERENCES `airport` (`airport_id`)
) ENGINE=InnoDB AUTO_INCREMENT=114 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Flughafen DB by Stefan Pröll, Eva Zangerle, Wolfgang Gassler is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0' SECONDARY_ENGINE=RAPID;
/*!40101 SET character_set_client = @saved_cs_client */;
