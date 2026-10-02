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
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("Error: pymysql is required. Install with: pip install pymysql")
    sys.exit(1)

logger = logging.getLogger(__name__)


class DatabaseSyncManager:
    """Manages synchronization between source and destination databases"""
    
    BATCH_SIZE = 300
    COMMIT_INTERVAL = 10  # Commit after every 10 batches (3000 rows)
    
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
        self.tables = []
        self.failed_tables = []

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
                cursorclass=pymysql.cursors.DictCursor,
                init_command='SET FOREIGN_KEY_CHECKS=0'
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
        """Warn that no backup is written: take one before a real run"""
        if self.dry_run:
            return
        logger.warning("This script writes no backup. Every table it copies is "
                       "emptied on the destination first: take an RDS snapshot or "
                       "a mysqldump of the destination before a real run.")

    def list_tables(self):
        """Every base table of the source database"""
        with self.source_conn.cursor(pymysql.cursors.Cursor) as cursor:
            cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            return [row[0] for row in cursor.fetchall()]

    def get_table_columns(self, table_name):
        """Get column names for a table"""
        try:
            with self.source_conn.cursor(pymysql.cursors.Cursor) as cursor:
                cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
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
                self.failed_tables.append(table_name)
                return 0
            
            column_str = ", ".join([f"`{col}`" for col in columns])
            placeholder_str = ", ".join(["%s"] * len(columns))
            
            if not self.dry_run:
                # Clear destination table
                with self.dest_conn.cursor() as cursor:
                    cursor.execute(f"DELETE FROM `{table_name}`")
                self.dest_conn.commit()
            
            # Count source rows
            with self.source_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
                total_rows = cursor.fetchone()['cnt']
            
            if total_rows == 0:
                logger.info(f"  No rows to sync")
                self.stats[table_name] = 0
                return 0
            
            logger.info(f"  Total rows: {total_rows}")
            
            # Fetch and insert data in batches
            rows_synced = 0
            batch_count = 0
            
            with self.source_conn.cursor(pymysql.cursors.SSDictCursor) as source_cursor:
                source_cursor.execute(f"SELECT {column_str} FROM `{table_name}`")

                while True:
                    rows = source_cursor.fetchmany(self.BATCH_SIZE)
                    if not rows:
                        break

                    batch_count += 1
                    rows_synced += len(rows)

                    if not self.dry_run:
                        insert_sql = f"INSERT INTO `{table_name}` ({column_str}) VALUES ({placeholder_str})"

                        with self.dest_conn.cursor() as dest_cursor:
                            dest_cursor.executemany(
                                insert_sql, [tuple(row[col] for col in columns) for row in rows])

                        # Commit every COMMIT_INTERVAL batches
                        if batch_count % self.COMMIT_INTERVAL == 0:
                            self.dest_conn.commit()
                            logger.info(f"  Progress: {rows_synced}/{total_rows} rows synced")

            # Final commit
            if not self.dry_run:
                self.dest_conn.commit()
            
            logger.info(f"  ✓ Synced {rows_synced} rows")
            self.stats[table_name] = rows_synced
            self.total_rows_synced += rows_synced
            
            return rows_synced
            
        except pymysql.Error as e:
            logger.error(f"Error syncing table {table_name}: {e}")
            self.failed_tables.append(table_name)
            if not self.dry_run:
                self.dest_conn.rollback()
            return 0
    
    def verify_sync(self):
        """Verify that source and destination have matching row counts"""
        logger.info("\n=== VERIFICATION ===")
        
        mismatches = []
        
        for table in self.tables:
            try:
                with self.source_conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                    source_count = cursor.fetchone()['cnt']

                with self.dest_conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                    dest_count = cursor.fetchone()['cnt']

                if self.dry_run:
                    logger.info(f"  {table}: source={source_count}, dest={dest_count} (dry run, not compared)")
                    continue

                status = "✓" if source_count == dest_count else "✗"
                logger.info(f"{status} {table}: source={source_count}, dest={dest_count}")
                
                if source_count != dest_count:
                    mismatches.append(table)
                    
            except Exception as e:
                logger.error(f"Error verifying {table}: {e}")
                mismatches.append(table)

        failed = [table for table in self.tables
                  if table in mismatches or table in self.failed_tables]
        if failed:
            logger.error(f"\nTables not copied or not matching: {', '.join(failed)}")
            return False
        elif self.dry_run:
            logger.info(f"\n✓ Every table can be read on both sides - dry run, nothing written")
            return True
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
            self.tables = self.list_tables()
            logger.info(f"Tables in the source: {len(self.tables)}")

            if not self.dry_run:
                self.backup_destination()

            # Sync each table
            for table in self.tables:
                self.sync_table(table)
            
            # Verify
            verified = self.verify_sync()

            # Final summary
            logger.info(f"\n{'='*60}")
            logger.info("Synchronization Complete" if verified else "Synchronization Failed")
            logger.info(f"Total rows synced: {self.total_rows_synced:,}")
            logger.info(f"{'='*60}\n")

            if not verified:
                sys.exit(1)

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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('db_sync.log'),
            logging.StreamHandler()
        ]
    )
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
                        help='JSON file with "source" and "destination" objects '
                             '(host, port, db, user, password), over the options above')
    
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
    
    if args.config:
        file_config = load_config_from_file(os.path.expanduser(args.config))
        if file_config is None:
            sys.exit(1)
        source_config.update(file_config.get('source', {}))
        dest_config.update(file_config.get('destination', {}))

    # Run sync
    sync_manager = DatabaseSyncManager(source_config, dest_config, dry_run=args.dry_run)
    sync_manager.run_sync()


if __name__ == '__main__':
    main()
