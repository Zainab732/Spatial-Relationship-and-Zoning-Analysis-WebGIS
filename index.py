import os
import psycopg2
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Initialize App
app = FastAPI(title="LZPA Seattle Zoning API")

# 2. Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Database Connection
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    # If on Vercel, use the environment variable. 
    # If local, use your hardcoded fallback.
    url = DATABASE_URL if DATABASE_URL else "postgresql://neondb_owner:npg_czl45FkUIALy@ep-delicate-wave-ah9pkohw-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
    return psycopg2.connect(url)

# Helper function to run SQL
def run_geo_query(query, params):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        return row[0] if row and row[0] else {"type": "FeatureCollection", "features": []}
    except Exception as e:
        return {"type": "FeatureCollection", "features": [], "error": str(e)}
    finally:
        cur.close()
        conn.close()

# ---------------------------------------------------------
# 4. API Endpoints (IMPORTANT: Added /api/ prefix for Vercel)
# ---------------------------------------------------------

@app.get("/api/python") # This is for testing
def health_check():
    return {"status": "Online", "message": "FastAPI is working on Vercel!"}

@app.get("/api/buildings")
def get_buildings(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(f), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, f.gid AS id, 
      ST_AsGeoJSON(ST_Transform(ST_SetSRID(f.geom, 2926), 4326))::jsonb AS geometry,
      jsonb_build_object(
          'pin', f.pin, 'use', f.comment_, 'zoning', COALESCE(z.zoning, 'Unzoned'),
          'status', CASE WHEN r.allowed_land_use IS NULL OR f.comment_ = r.allowed_land_use THEN 'Compliant' ELSE 'Conflict' END
      ) AS properties
      FROM building_footprint_2023 f
      LEFT JOIN seatle_zoning z ON ST_Intersects(ST_Centroid(ST_SetSRID(f.geom, 2926)), ST_SetSRID(z.geom, 2926))
      LEFT JOIN zoning_rules r ON z.zoning = r.zoning_code
      WHERE ST_SetSRID(f.geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926)
      LIMIT 1000
    ) AS f;
    """
    return run_geo_query(query, (min_lon, min_lat, max_lon, max_lat))

@app.get("/api/zoning")
def get_zoning(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(z), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, gid AS id, 
      ST_AsGeoJSON(ST_Transform(ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 4326))::jsonb AS geometry,
      jsonb_build_object('code', zoning, 'category', category_d) AS properties
      FROM seatle_zoning
      WHERE ST_SetSRID(geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926)
      LIMIT 100
    ) AS z;
    """
    return run_geo_query(query, (min_lon, min_lat, max_lon, max_lat))

@app.get("/api/parcels")
def get_parcels(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(p), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, gid AS id, 
      ST_AsGeoJSON(ST_Transform(ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 4326))::jsonb AS geometry,
      jsonb_build_object('name', name, 'city', citydst) AS properties
      FROM admin_parcels
      WHERE ST_SetSRID(geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926)
      LIMIT 100
    ) AS p;
    """
    return run_geo_query(query, (min_lon, min_lat, max_lon, max_lat))

# No runner block needed for Vercel
