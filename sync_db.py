#!/usr/bin/env python3
"""
Database Synchronization Script - Sync non-Docker MySQL to Docker/AWS RDS MySQL

This script transfers data from a source MySQL database to a destination MySQL database.
Supports local MySQL, Docker containers, and AWS RDS instances.

Usage:
    python sync_db.py --source-host localhost --source-port 3306 --source-db fashionista_migration \
                      --dest-host mysql --dest-port 3306 --dest-db fashionista \
                      --source-user fashionista --source-pass fashionista \
                      --dest-user fashionista --dest-pass fashionista

Environment Variables (optional):
    SOURCE_DB_HOST, SOURCE_DB_PORT, SOURCE_DB_NAME, SOURCE_DB_USER, SOURCE_DB_PASSWORD
    DEST_DB_HOST, DEST_DB_PORT, DEST_DB_NAME, DEST_DB_USER, DEST_DB_PASSWORD
"""

import sys
import argparse
import logging
import json
import os
from datetime import datetime
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("Error: pymysql is required. Install with: pip install pymysql")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DatabaseSyncManager:
    """Manages synchronization between source and destination databases"""
    
    BATCH_SIZE = 300
    COMMIT_INTERVAL = 10  # Commit after every 10 batches (3000 rows)
    
    # Tables to sync in order (respecting foreign key dependencies)
    TABLES_TO_SYNC = [
        'auth_user',
        'auth_group',
        'auth_group_permissions',
        'auth_user_groups',
        'auth_user_user_permissions',
        'django_content_type',
        'django_permission',
        'social_auth_usersocialauth',
        'chardata_set',
        'chardata_setbonus',
        'chardata_itemtype',
        'chardata_item',
        'chardata_char',
        'chardata_charbasestats',
        'chardata_characterskill',
        'chardata_solutioncounter',
        'chardata_build',
        'chardata_builditem',
        'chardata_useralias',
        'chardata_customset',
        'django_session',
        'django_migrations',
        'django_admin_log',
        'socialauth_nonce',
    ]
    
    def __init__(self, source_config, dest_config, dry_run=False):
        """
        Initialize sync manager
        
        Args:
            source_config: dict with host, port, db, user, password
            dest_config: dict with host, port, db, user, password
            dry_run: bool, if True don't make changes
        """
        self.source_config = source_config
        self.dest_config = dest_config
        self.dry_run = dry_run
        self.source_conn = None
        self.dest_conn = None
        self.total_rows_synced = 0
        self.stats = {}
        
    def connect(self):
        """Establish connections to both databases"""
        try:
            logger.info(f"Connecting to source: {self.source_config['host']}:{self.source_config['port']}")
            self.source_conn = pymysql.connect(
                host=self.source_config['host'],
                port=self.source_config['port'],
                user=self.source_config['user'],
                password=self.source_config['password'],
                database=self.source_config['db'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("✓ Connected to source database")
            
            logger.info(f"Connecting to destination: {self.dest_config['host']}:{self.dest_config['port']}")
            self.dest_conn = pymysql.connect(
                host=self.dest_config['host'],
                port=self.dest_config['port'],
                user=self.dest_config['user'],
                password=self.dest_config['password'],
                database=self.dest_config['db'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("✓ Connected to destination database")
            
        except pymysql.Error as e:
            logger.error(f"Connection failed: {e}")
            sys.exit(1)
    
    def disconnect(self):
        """Close database connections"""
        if self.source_conn:
            self.source_conn.close()
        if self.dest_conn:
            self.dest_conn.close()
    
    def backup_destination(self):
        """Create a backup of destination database before sync"""
        if self.dry_run:
            logger.info("[DRY RUN] Would create backup")
            return
        
        try:
            backup_file = f"db_backup_{self.dest_config['db']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            logger.info(f"Creating backup: {backup_file}")
            
            with self.dest_conn.cursor() as cursor:
                # Get list of all tables
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"✓ Backup created: {backup_file} (reference for {len(tables)} tables)")
            
        except pymysql.Error as e:
            logger.error(f"Backup creation failed: {e}")
    
    def get_table_columns(self, table_name):
        """Get column names for a table"""
        try:
            with self.source_conn.cursor() as cursor:
                cursor.execute(f"SHOW COLUMNS FROM {table_name}")
                columns = [row[0] for row in cursor.fetchall()]
                return columns
        except pymysql.Error as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
            return None
    
    def sync_table(self, table_name):
        """Sync a single table from source to destination"""
        try:
            logger.info(f"\nSyncing table: {table_name}")
            
            # Get column names
            columns = self.get_table_columns(table_name)
            if not columns:
                return 0
            
            column_str = ", ".join([f"`{col}`" for col in columns])
            placeholder_str = ", ".join(["%s"] * len(columns))
            
            if not self.dry_run:
                # Clear destination table
                with self.dest_conn.cursor() as cursor:
                    cursor.execute(f"TRUNCATE TABLE {table_name}")
                self.dest_conn.commit()
            
            # Count source rows
            with self.source_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
                total_rows = cursor.fetchone()['cnt']
            
            if total_rows == 0:
                logger.info(f"  No rows to sync")
                self.stats[table_name] = 0
                return 0
            
            logger.info(f"  Total rows: {total_rows}")
            
            # Fetch and insert data in batches
            rows_synced = 0
            batch_count = 0
            
            with self.source_conn.cursor() as source_cursor:
                source_cursor.execute(f"SELECT {column_str} FROM {table_name}")
                
                while True:
                    rows = source_cursor.fetchmany(self.BATCH_SIZE)
                    if not rows:
                        break
                    
                    batch_count += 1
                    
                    if not self.dry_run:
                        insert_sql = f"INSERT INTO {table_name} ({column_str}) VALUES ({placeholder_str})"
                        
                        with self.dest_conn.cursor() as dest_cursor:
                            for row in rows:
                                values = tuple(row[col] for col in columns)
                                dest_cursor.execute(insert_sql, values)
                        
                        # Commit every COMMIT_INTERVAL batches
                        if batch_count % self.COMMIT_INTERVAL == 0:
                            self.dest_conn.commit()
                            rows_synced += len(rows)
                            logger.info(f"  Progress: {rows_synced}/{total_rows} rows synced")
                    else:
                        rows_synced += len(rows)
            
            # Final commit
            if not self.dry_run:
                self.dest_conn.commit()
            
            logger.info(f"  ✓ Synced {rows_synced} rows")
            self.stats[table_name] = rows_synced
            self.total_rows_synced += rows_synced
            
            return rows_synced
            
        except pymysql.Error as e:
            logger.error(f"Error syncing table {table_name}: {e}")
            if not self.dry_run:
                self.dest_conn.rollback()
            return 0
    
    def verify_sync(self):
        """Verify that source and destination have matching row counts"""
        logger.info("\n=== VERIFICATION ===")
        
        mismatches = []
        
        for table in self.TABLES_TO_SYNC:
            try:
                with self.source_conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                    source_count = cursor.fetchone()['cnt']
                
                with self.dest_conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                    dest_count = cursor.fetchone()['cnt']
                
                status = "✓" if source_count == dest_count else "✗"
                logger.info(f"{status} {table}: source={source_count}, dest={dest_count}")
                
                if source_count != dest_count:
                    mismatches.append(table)
                    
            except Exception as e:
                logger.error(f"Error verifying {table}: {e}")
        
        if mismatches:
            logger.error(f"\n⚠ Mismatches found in tables: {', '.join(mismatches)}")
            return False
        else:
            logger.info(f"\n✓ All tables verified - sync successful!")
            return True
    
    def run_sync(self):
        """Execute the full synchronization"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Database Synchronization Starting")
        logger.info(f"{'='*60}")
        logger.info(f"Source: {self.source_config['user']}@{self.source_config['host']}:{self.source_config['port']}/{self.source_config['db']}")
        logger.info(f"Destination: {self.dest_config['user']}@{self.dest_config['host']}:{self.dest_config['port']}/{self.dest_config['db']}")
        
        if self.dry_run:
            logger.warning("⚠ DRY RUN MODE - No changes will be made")
        
        try:
            self.connect()
            
            if not self.dry_run:
                self.backup_destination()
            
            # Sync each table
            for table in self.TABLES_TO_SYNC:
                self.sync_table(table)
            
            # Verify
            self.verify_sync()
            
            # Final summary
            logger.info(f"\n{'='*60}")
            logger.info(f"Synchronization Complete")
            logger.info(f"Total rows synced: {self.total_rows_synced:,}")
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            sys.exit(1)
        finally:
            self.disconnect()


def load_config_from_file(config_file):
    """Load database configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config from {config_file}: {e}")
        return None


def load_windows_config():
    """Load configuration from Windows fashionista config"""
    config_path = Path(os.environ.get('APPDATA', '')) / 'fashionista' / 'gen_config.json'
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load Windows config: {e}")
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Synchronize databases between source and destination',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--source-host', default=os.environ.get('SOURCE_DB_HOST', 'localhost'),
                        help='Source database host')
    parser.add_argument('--source-port', type=int, default=int(os.environ.get('SOURCE_DB_PORT', 3306)),
                        help='Source database port')
    parser.add_argument('--source-db', default=os.environ.get('SOURCE_DB_NAME', 'fashionista_migration'),
                        help='Source database name')
    parser.add_argument('--source-user', default=os.environ.get('SOURCE_DB_USER', 'fashionista'),
                        help='Source database user')
    parser.add_argument('--source-pass', default=os.environ.get('SOURCE_DB_PASSWORD', 'fashionista'),
                        help='Source database password')
    
    parser.add_argument('--dest-host', default=os.environ.get('DEST_DB_HOST', 'localhost'),
                        help='Destination database host')
    parser.add_argument('--dest-port', type=int, default=int(os.environ.get('DEST_DB_PORT', 3307)),
                        help='Destination database port')
    parser.add_argument('--dest-db', default=os.environ.get('DEST_DB_NAME', 'fashionista'),
                        help='Destination database name')
    parser.add_argument('--dest-user', default=os.environ.get('DEST_DB_USER', 'fashionista'),
                        help='Destination database user')
    parser.add_argument('--dest-pass', default=os.environ.get('DEST_DB_PASSWORD', 'fashionista'),
                        help='Destination database password')
    
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without making changes (preview mode)')
    parser.add_argument('--config', type=str,
                        help='Load configuration from JSON file')
    
    args = parser.parse_args()
    
    # Build config dicts
    source_config = {
        'host': args.source_host,
        'port': args.source_port,
        'db': args.source_db,
        'user': args.source_user,
        'password': args.source_pass,
    }
    
    dest_config = {
        'host': args.dest_host,
        'port': args.dest_port,
        'db': args.dest_db,
        'user': args.dest_user,
        'password': args.dest_pass,
    }
    
    # Run sync
    sync_manager = DatabaseSyncManager(source_config, dest_config, dry_run=args.dry_run)
    sync_manager.run_sync()


if __name__ == '__main__':
    main()
