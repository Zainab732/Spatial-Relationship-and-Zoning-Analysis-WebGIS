import os
import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    # 1. Get URL from Vercel Environment Variables
    url = os.getenv("DATABASE_URL")
    
    # 2. If no environment variable, use the fallback
    if not url:
        url = "postgresql://neondb_owner:npg_czl45FkUIALy@ep-delicate-wave-ah9pkohw-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
    
    # 3. Force SSL (Required for Neon)
    if "sslmode" not in url:
        separator = "&" if "?" in url else "?"
        url += f"{separator}sslmode=require"
        
    return psycopg2.connect(url)

def run_query(query, params):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row and row[0] else {"type": "FeatureCollection", "features": []}
    except Exception as e:
        # This returns the error as JSON so the map doesn't crash
        return {"type": "FeatureCollection", "features": [], "error": str(e)}

@app.get("/api/buildings")
def get_buildings(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(f), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, f.gid AS id, ST_AsGeoJSON(ST_Transform(ST_SetSRID(f.geom, 2926), 4326))::jsonb AS geometry,
      jsonb_build_object('pin', pin, 'status', CASE WHEN r.allowed_land_use IS NULL OR f.comment_ = r.allowed_land_use THEN 'Compliant' ELSE 'Conflict' END) AS properties
      FROM building_footprint_2023 f
      LEFT JOIN seatle_zoning z ON ST_Intersects(ST_Centroid(ST_SetSRID(f.geom, 2926)), ST_SetSRID(z.geom, 2926))
      LEFT JOIN zoning_rules r ON z.zoning = r.zoning_code
      WHERE ST_SetSRID(f.geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926) LIMIT 200
    ) AS f;"""
    return run_query(query, (min_lon, min_lat, max_lon, max_lat))

@app.get("/api/zoning")
def get_zoning(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(z), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, gid AS id, ST_AsGeoJSON(ST_Transform(ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 4326))::jsonb AS geometry,
      jsonb_build_object('code', zoning, 'category', category_d) AS properties
      FROM seatle_zoning
      WHERE ST_SetSRID(geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926) LIMIT 50
    ) AS z;"""
    return run_query(query, (min_lon, min_lat, max_lon, max_lat))

@app.get("/api/parcels")
def get_parcels(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(p), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, gid AS id, ST_AsGeoJSON(ST_Transform(ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 4326))::jsonb AS geometry,
      jsonb_build_object('name', name, 'city', citydst) AS properties
      FROM admin_parcels
      WHERE ST_SetSRID(geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926) LIMIT 50
    ) AS p;"""
    return run_query(query, (min_lon, min_lat, max_lon, max_lat))
