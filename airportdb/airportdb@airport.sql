-- MySQLShell dump 2.0.1  Distrib Ver 9.3.0 for Linux on x86_64 - for MySQL 9.3.0 (MySQL Community Server (GPL)), for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: airportdb    Table: airport
-- ------------------------------------------------------
-- Server version	9.3.0

--
-- Current Database: `airportdb`
--

USE `airportdb`;

--
-- Table structure for table `airport`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `airport` (
  `airport_id` smallint NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for each airport.',
  `iata` char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Three-letter IATA airport code used in ticketing and flight planning .',
  `icao` char(4) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Four-letter ICAO airport code used for air traffic control and airline operations.',
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Full name of the airport.',
  PRIMARY KEY (`airport_id`),
  UNIQUE KEY `icao_unq` (`icao`),
  KEY `name_idx` (`name`),
  KEY `iata_idx` (`iata`)
) ENGINE=InnoDB AUTO_INCREMENT=13598 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Flughafen DB by Stefan Pröll, Eva Zangerle, Wolfgang Gassler is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0' SECONDARY_ENGINE=RAPID;
/*!40101 SET character_set_client = @saved_cs_client */;
