import pg from 'pg';

export function createPool(connectionString) {
  if (!connectionString) throw new Error('Задайте DATABASE_URL');
  const pool = new pg.Pool({ connectionString, max: 10, connectionTimeoutMillis: 5000 });
  pool.on('error', (error) => console.error('PostgreSQL pool error:', error.code));
  return pool;
}

export async function transaction(pool, fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}
