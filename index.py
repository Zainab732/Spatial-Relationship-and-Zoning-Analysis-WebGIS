import os
import psycopg2
import json
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
    # Use the variable from Vercel Settings
    url = os.getenv("DATABASE_URL")
    if not url:
        # Local fallback
        url = "postgresql://neondb_owner:npg_czl45FkUIALy@ep-delicate-wave-ah9pkohw-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
    return psycopg2.connect(url)

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

# IMPORTANT: Added /api/ to the start of every route for Vercel
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
      WHERE ST_SetSRID(f.geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926) LIMIT 500
    ) AS f;"""
    return run_geo_query(query, (min_lon, min_lat, max_lon, max_lat))

@app.get("/api/zoning")
def get_zoning(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(z), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, gid AS id, ST_AsGeoJSON(ST_Transform(ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 4326))::jsonb AS geometry,
      jsonb_build_object('code', zoning) AS properties
      FROM seatle_zoning
      WHERE ST_SetSRID(geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926) LIMIT 100
    ) AS z;"""
    return run_geo_query(query, (min_lon, min_lat, max_lon, max_lat))

@app.get("/api/parcels")
def get_parcels(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    query = """
    SELECT jsonb_build_object('type','FeatureCollection','features',COALESCE(jsonb_agg(p), '[]'::jsonb))
    FROM (
      SELECT 'Feature' AS type, gid AS id, ST_AsGeoJSON(ST_Transform(ST_Force2D(ST_MakeValid(ST_SetSRID(geom, 2926))), 4326))::jsonb AS geometry,
      jsonb_build_object('name', name) AS properties
      FROM admin_parcels
      WHERE ST_SetSRID(geom, 2926) && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 2926) LIMIT 100
    ) AS p;"""
    return run_geo_query(query, (min_lon, min_lat, max_lon, max_lat))
