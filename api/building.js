import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { min_lon, min_lat, max_lon, max_lat } = req.query;

  const query = `
    SELECT jsonb_build_object(
      'type', 'FeatureCollection',
      'features', COALESCE(jsonb_agg(f), '[]'::jsonb)
    )
    FROM (
      SELECT 
        'Feature' AS type,
        f.gid AS id,
        ST_AsGeoJSON(
          ST_Transform(ST_SetSRID(f.geom, 2926), 4326)
        )::jsonb AS geometry,
        jsonb_build_object(
          'pin', f.pin,
          'use', f.comment_,
          'zoning', COALESCE(z.zoning, 'Unzoned'),
          'status', CASE 
            WHEN r.allowed_land_use IS NULL OR f.comment_ = r.allowed_land_use 
            THEN 'Compliant' 
            ELSE 'Conflict' 
          END
        ) AS properties
      FROM building_footprint_2023 f
      LEFT JOIN seatle_zoning z 
        ON ST_Intersects(
          ST_Centroid(ST_SetSRID(f.geom, 2926)), 
          ST_SetSRID(z.geom, 2926)
        )
      LEFT JOIN zoning_rules r ON z.zoning = r.zoning_code
      WHERE ST_SetSRID(f.geom, 2926) && 
            ST_Transform(ST_MakeEnvelope($1, $2, $3, $4, 4326), 2926)
      LIMIT 1000
    ) AS f;
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
