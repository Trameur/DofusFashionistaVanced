try:
	import pymysql

	pymysql.install_as_MySQLdb()
except Exception:
	# Keep startup resilient if PyMySQL is not available yet.
	pass
