-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: fashionista
-- ------------------------------------------------------
-- Server version	8.0.45

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

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=81 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add user',4,'add_user'),(14,'Can change user',4,'change_user'),(15,'Can delete user',4,'delete_user'),(16,'Can view user',4,'view_user'),(17,'Can add content type',5,'add_contenttype'),(18,'Can change content type',5,'change_contenttype'),(19,'Can delete content type',5,'delete_contenttype'),(20,'Can view content type',5,'view_contenttype'),(21,'Can add session',6,'add_session'),(22,'Can change session',6,'change_session'),(23,'Can delete session',6,'delete_session'),(24,'Can view session',6,'view_session'),(25,'Can add association',7,'add_association'),(26,'Can change association',7,'change_association'),(27,'Can delete association',7,'delete_association'),(28,'Can view association',7,'view_association'),(29,'Can add code',8,'add_code'),(30,'Can change code',8,'change_code'),(31,'Can delete code',8,'delete_code'),(32,'Can view code',8,'view_code'),(33,'Can add nonce',9,'add_nonce'),(34,'Can change nonce',9,'change_nonce'),(35,'Can delete nonce',9,'delete_nonce'),(36,'Can view nonce',9,'view_nonce'),(37,'Can add user social auth',10,'add_usersocialauth'),(38,'Can change user social auth',10,'change_usersocialauth'),(39,'Can delete user social auth',10,'delete_usersocialauth'),(40,'Can view user social auth',10,'view_usersocialauth'),(41,'Can add partial',11,'add_partial'),(42,'Can change partial',11,'change_partial'),(43,'Can delete partial',11,'delete_partial'),(44,'Can view partial',11,'view_partial'),(45,'Can add char',12,'add_char'),(46,'Can change char',12,'change_char'),(47,'Can delete char',12,'delete_char'),(48,'Can view char',12,'view_char'),(49,'Can add char base stats',13,'add_charbasestats'),(50,'Can change char base stats',13,'change_charbasestats'),(51,'Can delete char base stats',13,'delete_charbasestats'),(52,'Can view char base stats',13,'view_charbasestats'),(53,'Can add user alias',14,'add_useralias'),(54,'Can change user alias',14,'change_useralias'),(55,'Can delete user alias',14,'delete_useralias'),(56,'Can view user alias',14,'view_useralias'),(57,'Can add item db version',15,'add_itemdbversion'),(58,'Can change item db version',15,'change_itemdbversion'),(59,'Can delete item db version',15,'delete_itemdbversion'),(60,'Can view item db version',15,'view_itemdbversion'),(61,'Can add solution counter',16,'add_solutioncounter'),(62,'Can change solution counter',16,'change_solutioncounter'),(63,'Can delete solution counter',16,'delete_solutioncounter'),(64,'Can view solution counter',16,'view_solutioncounter'),(65,'Can add solution memory',17,'add_solutionmemory'),(66,'Can change solution memory',17,'change_solutionmemory'),(67,'Can delete solution memory',17,'delete_solutionmemory'),(68,'Can view solution memory',17,'view_solutionmemory'),(69,'Can add solution memory hits',18,'add_solutionmemoryhits'),(70,'Can change solution memory hits',18,'change_solutionmemoryhits'),(71,'Can delete solution memory hits',18,'delete_solutionmemoryhits'),(72,'Can view solution memory hits',18,'view_solutionmemoryhits'),(73,'Can add build vote',19,'add_buildvote'),(74,'Can change build vote',19,'change_buildvote'),(75,'Can delete build vote',19,'delete_buildvote'),(76,'Can view build vote',19,'view_buildvote'),(77,'Can add build view',20,'add_buildview'),(78,'Can change build view',20,'change_buildview'),(79,'Can delete build view',20,'delete_buildview'),(80,'Can view build view',20,'view_buildview');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_groups`
--

DROP TABLE IF EXISTS `auth_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_groups`
--

LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_user_permissions`
--

DROP TABLE IF EXISTS `auth_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_user_permissions`
--

LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_buildview`
--

DROP TABLE IF EXISTS `chardata_buildview`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_buildview` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `ip_address` char(39) NOT NULL,
  `viewed_at` datetime(6) NOT NULL,
  `build_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `chardata_bu_build_i_b1da74_idx` (`build_id`,`ip_address`,`viewed_at`),
  CONSTRAINT `chardata_buildview_build_id_e814d0e9_fk_chardata_char_id` FOREIGN KEY (`build_id`) REFERENCES `chardata_char` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_buildview`
--

LOCK TABLES `chardata_buildview` WRITE;
/*!40000 ALTER TABLE `chardata_buildview` DISABLE KEYS */;
/*!40000 ALTER TABLE `chardata_buildview` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_buildvote`
--

DROP TABLE IF EXISTS `chardata_buildvote`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_buildvote` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `vote_type` varchar(10) NOT NULL,
  `created_time` datetime(6) NOT NULL,
  `build_id` bigint NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `chardata_buildvote_user_id_build_id_vote_type_8cb81537_uniq` (`user_id`,`build_id`,`vote_type`),
  KEY `chardata_bu_build_i_be05d1_idx` (`build_id`,`vote_type`),
  KEY `chardata_bu_user_id_f8cea4_idx` (`user_id`,`vote_type`),
  CONSTRAINT `chardata_buildvote_build_id_f4a6f74a_fk_chardata_char_id` FOREIGN KEY (`build_id`) REFERENCES `chardata_char` (`id`),
  CONSTRAINT `chardata_buildvote_user_id_2dab3f3d_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_buildvote`
--

LOCK TABLES `chardata_buildvote` WRITE;
/*!40000 ALTER TABLE `chardata_buildvote` DISABLE KEYS */;
/*!40000 ALTER TABLE `chardata_buildvote` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_char`
--

DROP TABLE IF EXISTS `chardata_char`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_char` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_time` datetime(6) DEFAULT NULL,
  `modified_time` datetime(6) DEFAULT NULL,
  `name` varchar(50) NOT NULL,
  `char_name` varchar(50) NOT NULL,
  `char_class` varchar(20) NOT NULL,
  `char_build` varchar(50) NOT NULL,
  `level` int NOT NULL,
  `minimum_stats` longblob NOT NULL,
  `minimum_crits` longblob NOT NULL,
  `stats_weight` longblob NOT NULL,
  `minimal_solution` longblob NOT NULL,
  `link_shared` tinyint(1) NOT NULL,
  `options` longblob NOT NULL,
  `inclusions` longblob NOT NULL,
  `exclusions` longblob NOT NULL,
  `aspects` longblob NOT NULL,
  `deleted` tinyint(1) NOT NULL,
  `allow_points_distribution` tinyint(1) NOT NULL,
  `owner_id` int DEFAULT NULL,
  `view_count` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `chardata_char_owner_id_681eeb67_fk_auth_user_id` (`owner_id`),
  CONSTRAINT `chardata_char_owner_id_681eeb67_fk_auth_user_id` FOREIGN KEY (`owner_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_char`
--

LOCK TABLES `chardata_char` WRITE;
/*!40000 ALTER TABLE `chardata_char` DISABLE KEYS */;
INSERT INTO `chardata_char` VALUES (1,'2026-04-18 16:08:57.036978','2026-04-18 16:09:30.891961','jhgjhgj 200','jhgjhgj','Forgelance','Cha',200,_binary '€•(\0\0\0\0\0\0\0}”(ŒAP”KŒMP”KŒRange”KŒSummon”Ku.','',_binary '€•\0\0\0\0\0\0}”(Œap”M`	Œmp”M`	Œrange”MÀŒlock”KdŒdodge”KdŒvit”KŒhp”KŒwis”K(Œstr”K\0Œint”K\0Œagi”KŒcha”KxŒpow”K@Œearthdam”K\0Œfiredam”K\0Œairdam”K\0Œwaterdam”M\ÐŒneutdam”K\0Œdam”M\ÐŒneutres”KŒ\nneutresper”K\ðŒearthres”KŒearthresper”K\ðŒfireres”KŒ\nfireresper”K\ðŒwaterres”KŒwaterresper”K\ðŒairres”KŒ	airresper”K\ðŒapred”K\0Œmpred”K0Œapres”KŒmpres”KŒheals”K\0Œpp”KŒinit”KŒpshdam”K\0Œsummon”K\0Œpshres”KŒcrires”KŒch”K\ðŒcridam”MDŒpermedam”M3Œ	perrandam”M\ÍŒ	perweadam”KÀŒ	perspedam”M@Œ	respermee”MhŒ	resperran”MHŒ	meleeness”K\0Œ	resperwea”MhŒ\npvpneutres”K\0Œpvpwaterres”K\0Œ	pvpairres”K\0Œ\npvpfireres”K\0Œpvpearthres”K\0Œ\rpvpneutresper”K\0Œpvpairresper”K\0Œ\rpvpfireresper”K\0Œpvpwaterresper”K\0Œpvpearthresper”K\0Œpod”K\0Œref”K\0Œtrapdam”K\0Œ\ntrapdamper”K\0Œcf”K\0u.',_binary '€•~\0\0\0\0\0\0Œfashionistapulp.modelresult”ŒModelResultMinimal”“”)”}”(Œ\ritem_per_slot”}”(Œpet”JO\Ä\0Œdofus1”M\×5Œring1”M…>Œboots”M†>Œdofus2”M{FŒring2”MNŒshield”M…OŒdofus3”MVŒamulet”M¸VŒcloak”M¹VŒhat”MºVŒweapon”M‡xŒbelt”MˆxŒdofus4”MƒŒdofus5”M\ËŒdofus6”MJuŒinput”}”(Œ\nchar_level”KÈŒbase_stats_by_attr”}”(ŒAP”KŒMP”KŒProspecting”KdŒPods”M\èŒSummon”KŒVitality”KdŒWisdom”KdŒStrength”KdŒIntelligence”KdŒChance”KdŒAgility”KduŒoptions”}”(Œap_exo”ˆŒ	range_exo”‰Œmp_exo”ˆŒdofus”ˆŒdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”ˆuŒorigin”Œ	generated”uŒstats”}”(Œvit”KŒwis”K\0Œint”K\0Œagi”K\0Œcha”MŽŒstr”K\0uub.',0,_binary '€•­\0\0\0\0\0\0}”(Œdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”ˆŒdofus”ˆŒdofuses”}”(Œochre”ˆŒvulbis”ˆŒice”ˆŒcrimson”ˆŒdolmanax”ˆŒcawwot”ˆŒemerald”ˆŒ	turquoise”ˆŒivory”ˆŒwatchers”ˆŒdokoko”ˆŒcloudy”ˆŒdotrich”ˆŒabyssal”ˆŒgrofus”ˆŒkaliptus”ˆŒ	lavasmith”ˆŒblackspotted”ˆŒebony”ˆŒsilver”ˆŒsparklingsilver”ˆŒcocoa”ˆŒdomakuro”ˆŒdorigami”ˆŒ	nightmare”ˆŒsylvan”ˆuŒdofusnotforchar”}”Œap_exo”ˆŒmp_exo”ˆŒ\nturq_dofus”ˆu.','',_binary '€•>\0\0\0\0\0\0\0]”(MG#M\î\ZM\ï\ZMkM¥IM!M–\"MjMýkM„jM’jMƒjMjM”jMŽjM‚jMjM9\ZM3e.',_binary '€•\0\0\0\0\0\0\0”(Œcha”.',1,1,NULL,0),(2,'2026-04-18 16:09:40.219437','2026-04-18 16:09:47.700323','erdytrdyhftjhgfh 199','erdytrdyhftjhgfh','Feca','Omni Dam',199,_binary '€•(\0\0\0\0\0\0\0}”(ŒAP”KŒMP”KŒRange”KŒSummon”Ku.','',_binary '€•\0\0\0\0\0\0}”(Œap”MV	Œmp”MV	Œrange”M¼Œlock”KxŒdodge”KPŒvit”KŒhp”KŒwis”K(Œstr”K(Œint”K(Œagi”K(Œcha”K(Œpow”KnŒearthdam”M\àŒfiredam”M\àŒairdam”M\àŒwaterdam”M\àŒneutdam”M\àŒdam”M`	Œneutres”KŒ\nneutresper”K\îŒearthres”KŒearthresper”K\îŒfireres”KŒ\nfireresper”K\îŒwaterres”KŒwaterresper”K\îŒairres”KŒ	airresper”K\îŒapred”K0Œmpred”K0Œapres”KŒmpres”KŒheals”K\0Œpp”KŒinit”KŒpshdam”K\0Œsummon”K\0Œpshres”KŒcrires”KŒch”K\ðŒcridam”MXŒpermedam”MŒ	perrandam”MŒ	perweadam”MGŒ	perspedam”M\ÜŒ	respermee”MeŒ	resperran”MAŒ	meleeness”K\0Œ	resperwea”MeŒ\npvpneutres”K\0Œpvpwaterres”K\0Œ	pvpairres”K\0Œ\npvpfireres”K\0Œpvpearthres”K\0Œ\rpvpneutresper”K\0Œpvpairresper”K\0Œ\rpvpfireresper”K\0Œpvpwaterresper”K\0Œpvpearthresper”K\0Œpod”K\0Œref”K\0Œtrapdam”K\0Œ\ntrapdamper”K\0Œcf”K\0u.',_binary '€•{\0\0\0\0\0\0Œfashionistapulp.modelresult”ŒModelResultMinimal”“”)”}”(Œ\ritem_per_slot”}”(Œpet”M™4Œbelt”Mƒ>Œring1”M„>Œdofus1”M\ÅZŒweapon”M|Œshield”M4|Œcloak”MAƒŒamulet”MBƒŒring2”MCƒŒdofus2”M¶Œdofus3”MƒŒdofus4”M\ÈŒdofus5”M\ËŒdofus6”MJŒboots”M\"Œhat”M\õ$uŒinput”}”(Œ\nchar_level”KÇŒbase_stats_by_attr”}”(ŒAP”KŒMP”KŒProspecting”KdŒPods”M\èŒSummon”KŒVitality”KdŒWisdom”KdŒStrength”KdŒIntelligence”KdŒChance”KdŒAgility”KduŒoptions”}”(Œap_exo”‰Œ	range_exo”‰Œmp_exo”‰Œdofus”ˆŒdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”‰uŒorigin”Œ	generated”uŒstats”}”(Œvit”K¾Œwis”K\0Œint”KdŒagi”KÈŒcha”KÈŒstr”Kduub.',0,_binary '€•­\0\0\0\0\0\0}”(Œdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”‰Œdofus”ˆŒdofuses”}”(Œochre”ˆŒvulbis”ˆŒice”ˆŒcrimson”ˆŒdolmanax”ˆŒcawwot”ˆŒemerald”ˆŒ	turquoise”ˆŒivory”ˆŒwatchers”ˆŒdokoko”ˆŒcloudy”ˆŒdotrich”ˆŒabyssal”ˆŒgrofus”ˆŒkaliptus”ˆŒ	lavasmith”ˆŒblackspotted”ˆŒebony”ˆŒsilver”ˆŒsparklingsilver”ˆŒcocoa”ˆŒdomakuro”ˆŒdorigami”ˆŒ	nightmare”ˆŒsylvan”ˆuŒdofusnotforchar”}”Œap_exo”‰Œmp_exo”‰Œ\nturq_dofus”ˆu.','',_binary '€•>\0\0\0\0\0\0\0]”(MG#M\î\ZM\ï\ZMkM¥IM!M–\"MjMýkM„jM’jMƒjMjM”jMŽjM‚jMjM9\ZM3e.',_binary '€•*\0\0\0\0\0\0\0”(Œint”Œcha”Œomni”Œdam”Œagi”Œstr”.',0,1,NULL,0);
/*!40000 ALTER TABLE `chardata_char` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_charbasestats`
--

DROP TABLE IF EXISTS `chardata_charbasestats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_charbasestats` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `stat` varchar(30) NOT NULL,
  `total_value` int NOT NULL,
  `scrolled_value` int NOT NULL,
  `char_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `chardata_charbasestats_char_id_35ddb9bc_fk` (`char_id`),
  CONSTRAINT `chardata_charbasestats_char_id_35ddb9bc_fk` FOREIGN KEY (`char_id`) REFERENCES `chardata_char` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_charbasestats`
--

LOCK TABLES `chardata_charbasestats` WRITE;
/*!40000 ALTER TABLE `chardata_charbasestats` DISABLE KEYS */;
INSERT INTO `chardata_charbasestats` VALUES (1,'Vitality',103,100,1),(2,'Wisdom',100,100,1),(3,'Strength',100,100,1),(4,'Intelligence',100,100,1),(5,'Chance',498,100,1),(6,'Agility',100,100,1),(7,'Vitality',290,100,2),(8,'Wisdom',100,100,2),(9,'Strength',200,100,2),(10,'Intelligence',200,100,2),(11,'Chance',300,100,2),(12,'Agility',300,100,2);
/*!40000 ALTER TABLE `chardata_charbasestats` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_itemdbversion`
--

DROP TABLE IF EXISTS `chardata_itemdbversion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_itemdbversion` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `dump_hash` varchar(255) NOT NULL,
  `created_time` date DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_itemdbversion`
--

LOCK TABLES `chardata_itemdbversion` WRITE;
/*!40000 ALTER TABLE `chardata_itemdbversion` DISABLE KEYS */;
/*!40000 ALTER TABLE `chardata_itemdbversion` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_solutioncounter`
--

DROP TABLE IF EXISTS `chardata_solutioncounter`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_solutioncounter` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `input_hash` bigint NOT NULL,
  `get_count` int NOT NULL,
  `created_time` datetime(6) DEFAULT NULL,
  `modified_time` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `chardata_solutioncounter_input_hash_1719fa05_uniq` (`input_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_solutioncounter`
--

LOCK TABLES `chardata_solutioncounter` WRITE;
/*!40000 ALTER TABLE `chardata_solutioncounter` DISABLE KEYS */;
INSERT INTO `chardata_solutioncounter` VALUES (1,-4173604671494487534,1,'2026-04-18 16:08:59.033117','2026-04-18 16:08:59.033134'),(2,-3781571355937955085,1,'2026-04-18 16:09:41.871225','2026-04-18 16:09:41.871237');
/*!40000 ALTER TABLE `chardata_solutioncounter` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_solutionmemory`
--

DROP TABLE IF EXISTS `chardata_solutionmemory`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_solutionmemory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `input_hash` bigint NOT NULL,
  `input` longblob NOT NULL,
  `stored` longblob NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `chardata_solutionmemory_input_hash_8c294bbb_uniq` (`input_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_solutionmemory`
--

LOCK TABLES `chardata_solutionmemory` WRITE;
/*!40000 ALTER TABLE `chardata_solutionmemory` DISABLE KEYS */;
INSERT INTO `chardata_solutionmemory` VALUES (1,-4173604671494487534,_binary '€•=\0\0\0\0\0\0Œfashionistapulp.model”Œ\nModelInput”“”)”}”(Œ\nchar_level”KÈŒbase_stats_by_attr”}”(ŒAP”KŒMP”KŒProspecting”KdŒPods”M\èŒSummon”KŒVitality”KdŒWisdom”KdŒStrength”KdŒIntelligence”KdŒChance”KdŒAgility”KduŒ\rminimum_stats”}”(ŒAP”KŒMP”KŒRange”KŒSummon”KuŒ\rlocked_equips”}”Œforbidden_equips””(MjM‚jMƒjM„jM3MŽjMjM’jM”jM–\"M¥IM9\ZMG#MjMkM\î\ZM\ï\ZMýkM!Œobjective_values”}”(Œap”M`	Œmp”M`	Œrange”MÀŒlock”KdŒdodge”KdŒvit”KŒhp”KŒwis”K(Œstr”K\0Œint”K\0Œagi”KŒcha”KxŒpow”K@Œearthdam”K\0Œfiredam”K\0Œairdam”K\0Œwaterdam”M\ÐŒneutdam”K\0Œdam”M\ÐŒneutres”KŒ\nneutresper”K\ðŒearthres”KŒearthresper”K\ðŒfireres”KŒ\nfireresper”K\ðŒwaterres”KŒwaterresper”K\ðŒairres”KŒ	airresper”K\ðŒapred”K\0Œmpred”K0Œapres”KŒmpres”KŒheals”K\0Œpp”KŒinit”KŒpshdam”K\0Œsummon”K\0Œpshres”KŒcrires”KŒch”K\ðŒcridam”MDŒpermedam”M3Œ	perrandam”M\ÍŒ	perweadam”KÀŒ	perspedam”M@Œ	respermee”MhŒ	resperran”MHŒ	meleeness”K\0Œ	resperwea”MhŒ\npvpneutres”K\0Œpvpwaterres”K\0Œ	pvpairres”K\0Œ\npvpfireres”K\0Œpvpearthres”K\0Œ\rpvpneutresper”K\0Œpvpairresper”K\0Œ\rpvpfireresper”K\0Œpvpwaterresper”K\0Œpvpearthresper”K\0Œpod”K\0Œref”K\0Œtrapdam”K\0Œ\ntrapdamper”K\0Œcf”K\0uŒoptions”}”(Œap_exo”ˆŒ	range_exo”‰Œmp_exo”ˆŒdofus”ˆŒdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”ˆuŒ\nchar_class”Œ\nForgelance”Œstat_points_to_distribute”M\ãub.',_binary '€•§\0\0\0\0\0\0ŒOptimal”}”(Œvit”KŒwis”K\0Œint”K\0Œagi”K\0Œcha”MŽŒstr”K\0uŒfashionistapulp.modelresult”ŒModelResultMinimal”“”)”}”(Œ\ritem_per_slot”}”(Œpet”JO\Ä\0Œdofus1”M\×5Œring1”M…>Œboots”M†>Œdofus2”M{FŒring2”MNŒshield”M…OŒdofus3”MVŒamulet”M¸VŒcloak”M¹VŒhat”MºVŒweapon”M‡xŒbelt”MˆxŒdofus4”MƒŒdofus5”M\ËŒdofus6”MJuŒinput”}”(Œ\nchar_level”KÈŒbase_stats_by_attr”}”(ŒAP”KŒMP”KŒProspecting”KdŒPods”M\èŒSummon”KŒVitality”KdŒWisdom”KdŒStrength”KdŒIntelligence”KdŒChance”KdŒAgility”KduŒoptions”}”(Œap_exo”ˆŒ	range_exo”‰Œmp_exo”ˆŒdofus”ˆŒdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”ˆuŒorigin”Œ	generated”uŒstats”}”(hKhK\0hK\0hK\0hMŽhK\0uub‡”.'),(2,-3781571355937955085,_binary '€•<\0\0\0\0\0\0Œfashionistapulp.model”Œ\nModelInput”“”)”}”(Œ\nchar_level”KÇŒbase_stats_by_attr”}”(ŒAP”KŒMP”KŒProspecting”KdŒPods”M\èŒSummon”KŒVitality”KdŒWisdom”KdŒStrength”KdŒIntelligence”KdŒChance”KdŒAgility”KduŒ\rminimum_stats”}”(ŒAP”KŒMP”KŒRange”KŒSummon”KuŒ\rlocked_equips”}”Œforbidden_equips””(MjM‚jMƒjM„jM3MŽjMjM’jM”jM–\"M¥IM9\ZMG#MjMkM\î\ZM\ï\ZMýkM!Œobjective_values”}”(Œap”MV	Œmp”MV	Œrange”M¼Œlock”KxŒdodge”KPŒvit”KŒhp”KŒwis”K(Œstr”K(Œint”K(Œagi”K(Œcha”K(Œpow”KnŒearthdam”M\àŒfiredam”M\àŒairdam”M\àŒwaterdam”M\àŒneutdam”M\àŒdam”M`	Œneutres”KŒ\nneutresper”K\îŒearthres”KŒearthresper”K\îŒfireres”KŒ\nfireresper”K\îŒwaterres”KŒwaterresper”K\îŒairres”KŒ	airresper”K\îŒapred”K0Œmpred”K0Œapres”KŒmpres”KŒheals”K\0Œpp”KŒinit”KŒpshdam”K\0Œsummon”K\0Œpshres”KŒcrires”KŒch”K\ðŒcridam”MXŒpermedam”MŒ	perrandam”MŒ	perweadam”MGŒ	perspedam”M\ÜŒ	respermee”MeŒ	resperran”MAŒ	meleeness”K\0Œ	resperwea”MeŒ\npvpneutres”K\0Œpvpwaterres”K\0Œ	pvpairres”K\0Œ\npvpfireres”K\0Œpvpearthres”K\0Œ\rpvpneutresper”K\0Œpvpairresper”K\0Œ\rpvpfireresper”K\0Œpvpwaterresper”K\0Œpvpearthresper”K\0Œpod”K\0Œref”K\0Œtrapdam”K\0Œ\ntrapdamper”K\0Œcf”K\0uŒoptions”}”(Œap_exo”‰Œ	range_exo”‰Œmp_exo”‰Œdofus”ˆŒdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”‰uŒ\nchar_class”ŒFeca”Œstat_points_to_distribute”M\Þub.',_binary '€•£\0\0\0\0\0\0ŒOptimal”}”(Œvit”K¾Œwis”K\0Œint”KdŒagi”KÈŒcha”KÈŒstr”KduŒfashionistapulp.modelresult”ŒModelResultMinimal”“”)”}”(Œ\ritem_per_slot”}”(Œpet”M™4Œbelt”Mƒ>Œring1”M„>Œdofus1”M\ÅZŒweapon”M|Œshield”M4|Œcloak”MAƒŒamulet”MBƒŒring2”MCƒŒdofus2”M¶Œdofus3”MƒŒdofus4”M\ÈŒdofus5”M\ËŒdofus6”MJŒboots”M\"Œhat”M\õ$uŒinput”}”(Œ\nchar_level”KÇŒbase_stats_by_attr”}”(ŒAP”KŒMP”KŒProspecting”KdŒPods”M\èŒSummon”KŒVitality”KdŒWisdom”KdŒStrength”KdŒIntelligence”KdŒChance”KdŒAgility”KduŒoptions”}”(Œap_exo”‰Œ	range_exo”‰Œmp_exo”‰Œdofus”ˆŒdragoturkey”ˆŒseemyool”ˆŒ	rhineetle”ˆŒprysmaradite”‰uŒorigin”Œ	generated”uŒstats”}”(hK¾hK\0hKdhK\ÈhK\ÈhKduub‡”.');
/*!40000 ALTER TABLE `chardata_solutionmemory` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_solutionmemoryhits`
--

DROP TABLE IF EXISTS `chardata_solutionmemoryhits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_solutionmemoryhits` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `count_hit` bigint NOT NULL,
  `count_miss` bigint NOT NULL,
  `day` date NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `chardata_solutionmemoryhits_day_12215871_uniq` (`day`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_solutionmemoryhits`
--

LOCK TABLES `chardata_solutionmemoryhits` WRITE;
/*!40000 ALTER TABLE `chardata_solutionmemoryhits` DISABLE KEYS */;
INSERT INTO `chardata_solutionmemoryhits` VALUES (1,0,2,'2026-04-18');
/*!40000 ALTER TABLE `chardata_solutionmemoryhits` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chardata_useralias`
--

DROP TABLE IF EXISTS `chardata_useralias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chardata_useralias` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `alias` varchar(50) DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `chardata_useralias_user_id_75bb3629_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chardata_useralias`
--

LOCK TABLES `chardata_useralias` WRITE;
/*!40000 ALTER TABLE `chardata_useralias` DISABLE KEYS */;
/*!40000 ALTER TABLE `chardata_useralias` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'auth','user'),(20,'chardata','buildview'),(19,'chardata','buildvote'),(12,'chardata','char'),(13,'chardata','charbasestats'),(15,'chardata','itemdbversion'),(16,'chardata','solutioncounter'),(17,'chardata','solutionmemory'),(18,'chardata','solutionmemoryhits'),(14,'chardata','useralias'),(5,'contenttypes','contenttype'),(6,'sessions','session'),(7,'social_django','association'),(8,'social_django','code'),(9,'social_django','nonce'),(11,'social_django','partial'),(10,'social_django','usersocialauth');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=55 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2026-04-18 16:06:31.118096'),(2,'auth','0001_initial','2026-04-18 16:06:32.546202'),(3,'admin','0001_initial','2026-04-18 16:06:32.828117'),(4,'admin','0002_logentry_remove_auto_add','2026-04-18 16:06:32.839906'),(5,'admin','0003_logentry_add_action_flag_choices','2026-04-18 16:06:32.850376'),(6,'contenttypes','0002_remove_content_type_name','2026-04-18 16:06:33.055409'),(7,'auth','0002_alter_permission_name_max_length','2026-04-18 16:06:33.195020'),(8,'auth','0003_alter_user_email_max_length','2026-04-18 16:06:33.223689'),(9,'auth','0004_alter_user_username_opts','2026-04-18 16:06:33.234593'),(10,'auth','0005_alter_user_last_login_null','2026-04-18 16:06:33.353493'),(11,'auth','0006_require_contenttypes_0002','2026-04-18 16:06:33.361593'),(12,'auth','0007_alter_validators_add_error_messages','2026-04-18 16:06:33.372324'),(13,'auth','0008_alter_user_username_max_length','2026-04-18 16:06:33.524046'),(14,'auth','0009_alter_user_last_name_max_length','2026-04-18 16:06:33.674273'),(15,'auth','0010_alter_group_name_max_length','2026-04-18 16:06:33.702209'),(16,'auth','0011_update_proxy_permissions','2026-04-18 16:06:33.713851'),(17,'auth','0012_alter_user_first_name_max_length','2026-04-18 16:06:33.851495'),(18,'chardata','0001_initial','2026-04-18 16:06:34.344303'),(19,'chardata','0002_auto_20160508_0202','2026-04-18 16:06:34.537177'),(20,'chardata','0003_auto_20160508_2029','2026-04-18 16:06:34.646919'),(21,'chardata','0004_auto_20160511_1717','2026-04-18 16:06:34.868539'),(22,'chardata','0005_adshits','2026-04-18 16:06:34.930703'),(23,'chardata','0006_auto_20170718_1902','2026-04-18 16:06:34.975677'),(24,'chardata','0007_delete_adshits','2026-04-18 16:06:35.014776'),(25,'chardata','0008_alter_char_id_alter_char_owner_and_more','2026-04-18 16:06:36.220008'),(26,'chardata','0009_char_view_count','2026-04-18 16:06:36.347093'),(27,'chardata','0010_buildvote','2026-04-18 16:06:36.816428'),(28,'chardata','0011_buildview','2026-04-18 16:06:37.009865'),(29,'chardata','0012_alter_char_created_time_alter_char_modified_time_and_more','2026-04-18 16:06:37.515893'),(30,'sessions','0001_initial','2026-04-18 16:06:37.602437'),(31,'default','0001_initial','2026-04-18 16:06:38.094675'),(32,'social_auth','0001_initial','2026-04-18 16:06:38.103046'),(33,'default','0002_add_related_name','2026-04-18 16:06:38.118298'),(34,'social_auth','0002_add_related_name','2026-04-18 16:06:38.125991'),(35,'default','0003_alter_email_max_length','2026-04-18 16:06:38.149718'),(36,'social_auth','0003_alter_email_max_length','2026-04-18 16:06:38.157158'),(37,'default','0004_auto_20160423_0400','2026-04-18 16:06:38.170679'),(38,'social_auth','0004_auto_20160423_0400','2026-04-18 16:06:38.178076'),(39,'social_auth','0005_auto_20160727_2333','2026-04-18 16:06:38.223804'),(40,'social_django','0006_partial','2026-04-18 16:06:38.304948'),(41,'social_django','0007_code_timestamp','2026-04-18 16:06:38.448546'),(42,'social_django','0008_partial_timestamp','2026-04-18 16:06:38.588319'),(43,'social_django','0009_auto_20191118_0520','2026-04-18 16:06:38.850688'),(44,'social_django','0010_uid_db_index','2026-04-18 16:06:38.894325'),(45,'social_django','0011_alter_id_fields','2026-04-18 16:06:39.612682'),(46,'social_django','0012_usersocialauth_extra_data_new','2026-04-18 16:06:39.900343'),(47,'social_django','0013_migrate_extra_data','2026-04-18 16:06:39.919775'),(48,'social_django','0014_remove_usersocialauth_extra_data','2026-04-18 16:06:40.134529'),(49,'social_django','0015_rename_extra_data_new_usersocialauth_extra_data','2026-04-18 16:06:40.204108'),(50,'social_django','0002_add_related_name','2026-04-18 16:06:40.212370'),(51,'social_django','0001_initial','2026-04-18 16:06:40.221301'),(52,'social_django','0003_alter_email_max_length','2026-04-18 16:06:40.227865'),(53,'social_django','0005_auto_20160727_2333','2026-04-18 16:06:40.234526'),(54,'social_django','0004_auto_20160423_0400','2026-04-18 16:06:40.241242');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('rqsc7x6wdryhnt2y69wsej9q1js4qt6h','eyJjaGFyX2lkIjoyfQ:1wE8Em:Ao6s4AJgL0JcD4gqcYBh4wKwBDSzukZNvFZyNuw3idw','2026-05-02 16:09:40.297672');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `social_auth_association`
--

DROP TABLE IF EXISTS `social_auth_association`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `social_auth_association` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `server_url` varchar(255) NOT NULL,
  `handle` varchar(255) NOT NULL,
  `secret` varchar(255) NOT NULL,
  `issued` int NOT NULL,
  `lifetime` int NOT NULL,
  `assoc_type` varchar(64) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `social_auth_association_server_url_handle_078befa2_uniq` (`server_url`,`handle`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `social_auth_association`
--

LOCK TABLES `social_auth_association` WRITE;
/*!40000 ALTER TABLE `social_auth_association` DISABLE KEYS */;
/*!40000 ALTER TABLE `social_auth_association` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `social_auth_code`
--

DROP TABLE IF EXISTS `social_auth_code`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `social_auth_code` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(254) NOT NULL,
  `code` varchar(32) NOT NULL,
  `verified` tinyint(1) NOT NULL,
  `timestamp` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `social_auth_code_email_code_801b2d02_uniq` (`email`,`code`),
  KEY `social_auth_code_code_a2393167` (`code`),
  KEY `social_auth_code_timestamp_176b341f` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `social_auth_code`
--

LOCK TABLES `social_auth_code` WRITE;
/*!40000 ALTER TABLE `social_auth_code` DISABLE KEYS */;
/*!40000 ALTER TABLE `social_auth_code` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `social_auth_nonce`
--

DROP TABLE IF EXISTS `social_auth_nonce`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `social_auth_nonce` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `server_url` varchar(255) NOT NULL,
  `timestamp` int NOT NULL,
  `salt` varchar(65) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `social_auth_nonce_server_url_timestamp_salt_f6284463_uniq` (`server_url`,`timestamp`,`salt`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `social_auth_nonce`
--

LOCK TABLES `social_auth_nonce` WRITE;
/*!40000 ALTER TABLE `social_auth_nonce` DISABLE KEYS */;
/*!40000 ALTER TABLE `social_auth_nonce` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `social_auth_partial`
--

DROP TABLE IF EXISTS `social_auth_partial`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `social_auth_partial` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `token` varchar(32) NOT NULL,
  `next_step` smallint unsigned NOT NULL,
  `backend` varchar(32) NOT NULL,
  `timestamp` datetime(6) NOT NULL,
  `data` json NOT NULL DEFAULT (_utf8mb4'{}'),
  PRIMARY KEY (`id`),
  KEY `social_auth_partial_token_3017fea3` (`token`),
  KEY `social_auth_partial_timestamp_50f2119f` (`timestamp`),
  CONSTRAINT `social_auth_partial_chk_1` CHECK ((`next_step` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `social_auth_partial`
--

LOCK TABLES `social_auth_partial` WRITE;
/*!40000 ALTER TABLE `social_auth_partial` DISABLE KEYS */;
/*!40000 ALTER TABLE `social_auth_partial` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `social_auth_usersocialauth`
--

DROP TABLE IF EXISTS `social_auth_usersocialauth`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `social_auth_usersocialauth` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `provider` varchar(32) NOT NULL,
  `uid` varchar(255) NOT NULL,
  `user_id` int NOT NULL,
  `created` datetime(6) NOT NULL,
  `modified` datetime(6) NOT NULL,
  `extra_data` json NOT NULL DEFAULT (_utf8mb4'{}'),
  PRIMARY KEY (`id`),
  UNIQUE KEY `social_auth_usersocialauth_provider_uid_e6b5e668_uniq` (`provider`,`uid`),
  KEY `social_auth_usersocialauth_user_id_17d28448_fk_auth_user_id` (`user_id`),
  KEY `social_auth_usersocialauth_uid_796e51dc` (`uid`),
  CONSTRAINT `social_auth_usersocialauth_user_id_17d28448_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `social_auth_usersocialauth`
--

LOCK TABLES `social_auth_usersocialauth` WRITE;
/*!40000 ALTER TABLE `social_auth_usersocialauth` DISABLE KEYS */;
/*!40000 ALTER TABLE `social_auth_usersocialauth` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-18 16:24:17
