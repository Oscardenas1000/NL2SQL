-- MySQLShell dump 2.0.1  Distrib Ver 9.3.0 for Linux on x86_64 - for MySQL 9.3.0 (MySQL Community Server (GPL)), for Linux (x86_64)
--
-- Host: 10.0.1.54    Database: airportdb    Table: airport_geo
-- ------------------------------------------------------
-- Server version	9.3.0

--
-- Current Database: `airportdb`
--

USE `airportdb`;

--
-- Table structure for table `airport_geo`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `airport_geo` (
  `airport_id` smallint NOT NULL COMMENT 'Identifier linking to the corresponding airport in the airport table.',
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Name of the airport.',
  `city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'City where the airport is located.',
  `country` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Country where the airport is located.',
  `latitude` decimal(11,8) NOT NULL COMMENT 'Latitude coordinate of the airport''s geographic location.',
  `longitude` decimal(11,8) NOT NULL COMMENT 'Longitude coordinate of the airport''s geographic location.',
  `geolocation` point NOT NULL NOT SECONDARY COMMENT 'MySQL POINT object combining latitude and longitude for geospatial queries.',
  PRIMARY KEY (`airport_id`),
  SPATIAL KEY `geolocation_spt` (`geolocation`),
  CONSTRAINT `airport_geo_ibfk_1` FOREIGN KEY (`airport_id`) REFERENCES `airport` (`airport_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Flughafen DB by Stefan Pröll, Eva Zangerle, Wolfgang Gassler is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0' SECONDARY_ENGINE=RAPID;
/*!40101 SET character_set_client = @saved_cs_client */;
