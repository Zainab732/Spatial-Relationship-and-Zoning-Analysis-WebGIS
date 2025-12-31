import { Pool } from 'pg';

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

export default async function handler(req, res) {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { min_lon, min_lat, max_lon, max_lat } = req.query;

  const query = `
    SELECT jsonb_build_object(
      'type', 'FeatureCollection',
      'features', COALESCE(jsonb_agg(p), '[]'::jsonb)
    )
    FROM (
      SELECT 
        'Feature' AS type,
        gid AS id,
        ST_AsGeoJSON(
          ST_Transform(
            ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 
            4326
          )
        )::jsonb AS geometry,
        jsonb_build_object(
          'name', name,
          'city', citydst
        ) AS properties
      FROM admin_parcels
      WHERE ST_SetSRID(geom, 2926) && 
            ST_Transform(ST_MakeEnvelope($1, $2, $3, $4, 4326), 2926)
      LIMIT 100
    ) AS p;
  `;

  try {
    const result = await pool.query(query, [min_lon, min_lat, max_lon, max_lat]);
    const geojson = result.rows[0].jsonb_build_object;
    res.status(200).json(geojson);
  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      type: 'FeatureCollection', 
      features: [], 
      error: error.message 
    });
  }
}
