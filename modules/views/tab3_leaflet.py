import json
from modules.services.geo_service import get_leaflet_logo_dict

def render_tab3_manual_leaflet_picker_html(lat, lng, is_dark_mode=False):
    """Renders an interactive Leaflet map picker for manual coordinate selection with native top-right layer switcher."""
    lat_val = float(lat) if lat and lat != 0 else 13.7651
    lng_val = float(lng) if lng and lng != 0 else 100.5383
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap');
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #picker-map {{
                width: 100%;
                height: 100vh;
                min-height: 480px;
                margin: 0;
                padding: 0;
                font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {'#0f172a' if is_dark_mode else '#f8fafc'};
                border-radius: 14px;
            }}
            .custom-picker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 40px;
                height: 40px;
                background: #ef4444;
                border-radius: 50%;
                border: 3.5px solid #ffffff;
                box-shadow: 0 4px 16px rgba(239, 68, 68, 0.45);
                cursor: grab;
                animation: pulsePin 2.2s infinite ease-in-out;
            }}
            .custom-picker-pin:active {{
                cursor: grabbing;
            }}
            @keyframes pulsePin {{
                0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); transform: scale(1); }}
                50% {{ box-shadow: 0 0 0 14px rgba(239, 68, 68, 0); transform: scale(1.05); }}
                100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); transform: scale(1); }}
            }}
            .custom-picker-pin-inner {{
                width: 12px;
                height: 12px;
                background: #ffffff;
                border-radius: 50%;
            }}
            .coord-floating-bar {{
                position: absolute;
                bottom: 16px;
                left: 16px;
                z-index: 1000;
                background: {'rgba(15, 23, 42, 0.88)' if is_dark_mode else 'rgba(255, 255, 255, 0.94)'};
                backdrop-filter: blur(10px);
                border: 1px solid {'rgba(255, 255, 255, 0.12)' if is_dark_mode else 'rgba(0, 0, 0, 0.08)'};
                border-radius: 12px;
                padding: 9px 16px;
                font-size: 13px;
                box-shadow: 0 6px 20px rgba(0,0,0,0.15);
                color: {'#f8fafc' if is_dark_mode else '#0f172a'};
                display: flex;
                align-items: center;
                gap: 12px;
                pointer-events: auto;
            }}
            .leaflet-control-layers {{
                border-radius: 12px !important;
                box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
                border: 1px solid #e2e8f0 !important;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif !important;
                font-size: 12.5px !important;
                padding: 6px !important;
            }}
            .leaflet-control-layers-base label {{
                color: #1e293b !important;
                margin-bottom: 4px !important;
                cursor: pointer !important;
                display: flex !important;
                align-items: center !important;
                gap: 6px !important;
            }}
            .copy-btn {{
                background: #059669;
                color: #ffffff;
                border: none;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 11.5px;
                font-weight: 700;
                cursor: pointer;
                transition: background 0.15s ease;
            }}
            .copy-btn:hover {{
                background: #047857;
            }}
        </style>
    </head>
    <body>
        <div id="picker-map"></div>
        <div class="coord-floating-bar" id="coordBar">
            <span><b>พิกัดที่เลือก:</b> <span id="latlngDisplay" style="font-weight:800; color:#ef4444; font-family:'Inter', monospace;">{lat_val:.6f}, {lng_val:.6f}</span></span>
            <span style="color:{'#94a3b8' if is_dark_mode else '#64748b'}; font-size:11.5px;">(คลิกหรือลากหมุดบนแผนที่เพื่อเปลี่ยนจุด)</span>
            <button type="button" class="copy-btn" onclick="copyCoord()">คัดลอก</button>
        </div>
        <script>
            var curLat = {lat_val};
            var curLng = {lng_val};

            var map = L.map('picker-map', {{
                zoomControl: true,
                attributionControl: false
            }}).setView([curLat, curLng], 12);

            var streetLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var osmLayer = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }});
            var satLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var topoLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var darkLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ maxZoom: 19 }});

            streetLayer.addTo(map);

            var baseMaps = {{
                "แผนที่ถนนมาตรฐาน (Esri Street)": streetLayer,
                "OpenStreetMap": osmLayer,
                "ภาพถ่ายดาวเทียม (Satellite)": satLayer,
                "ภูมิประเทศ (Topographic)": topoLayer,
                "โหมดมืด (Dark Canvas)": darkLayer
            }};
            L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

            var pickerIcon = L.divIcon({{
                className: 'custom-picker-icon',
                html: '<div class="custom-picker-pin"><div class="custom-picker-pin-inner"></div></div>',
                iconSize: [40, 40],
                iconAnchor: [20, 20],
                popupAnchor: [0, -20]
            }});

            var marker = L.marker([curLat, curLng], {{ icon: pickerIcon, draggable: true }}).addTo(map);

            function updateCoord(lat, lng, openPop) {{
                curLat = lat;
                curLng = lng;
                document.getElementById('latlngDisplay').innerText = lat.toFixed(6) + ', ' + lng.toFixed(6);
                marker.setLatLng([lat, lng]);
                
                var popupContent = '<div style="font-size:13px; font-weight:800; color:#ef4444; margin-bottom:3px;">จุดอ้างอิงของคุณ</div>' +
                    '<div style="font-size:12px; color:#334155;">ละติจูด: <b>' + lat.toFixed(6) + '</b><br/>ลองจิจูด: <b>' + lng.toFixed(6) + '</b></div>' +
                    '<div style="margin-top:6px; font-size:11px; color:#64748b;">ระบบตั้งค่าพิกัดนี้เป็นจุดอ้างอิงแล้ว</div>';
                marker.bindPopup(popupContent);
                if (openPop) marker.openPopup();

                try {{
                    var parentDoc = window.parent.document;
                    var nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
                    var containers = parentDoc.querySelectorAll('[data-testid="stNumberInput"]');
                    containers.forEach(function(container) {{
                        var labelEl = container.querySelector('label, p');
                        var inputEl = container.querySelector('input');
                        if (!labelEl || !inputEl) return;
                        var t = (labelEl.textContent || '').toLowerCase();
                        if (t.indexOf('latitude') !== -1 || t.indexOf('ละติจูด') !== -1) {{
                            nativeSetter.call(inputEl, lat.toFixed(6));
                            inputEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }} else if (t.indexOf('longitude') !== -1 || t.indexOf('ลองจิจูด') !== -1) {{
                            nativeSetter.call(inputEl, lng.toFixed(6));
                            inputEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }});
                }} catch(e) {{}}
            }}

            function copyCoord() {{
                var txt = curLat.toFixed(6) + ', ' + curLng.toFixed(6);
                navigator.clipboard.writeText(txt).then(function() {{
                    var btn = document.querySelector('.copy-btn');
                    btn.innerText = 'คัดลอกแล้ว!';
                    setTimeout(function() {{ btn.innerText = 'คัดลอก'; }}, 1800);
                }});
            }}

            marker.on('dragend', function(e) {{
                var pos = e.target.getLatLng();
                updateCoord(pos.lat, pos.lng, true);
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set('_clat', pos.lat.toFixed(6));
                    url.searchParams.set('_clng', pos.lng.toFixed(6));
                    window.parent.history.replaceState({{}}, '', url.toString());
                }} catch(e2) {{}}
            }});

            map.on('click', function(e) {{
                updateCoord(e.latlng.lat, e.latlng.lng, true);
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set('_clat', e.latlng.lat.toFixed(6));
                    url.searchParams.set('_clng', e.latlng.lng.toFixed(6));
                    window.parent.history.replaceState({{}}, '', url.toString());
                }} catch(e2) {{}}
            }});

            setTimeout(function() {{ map.invalidateSize(); }}, 250);
            window.addEventListener('resize', function() {{ map.invalidateSize(); }});
        </script>
    </body>
    </html>
    """
    return html

def render_tab3_radius_leaflet_map_html(inp_lat, inp_lng, search_radius_km, nearby_props, is_dark_mode=False, color_mode="จำแนกตามบริษัท (By Company)", tile_style="มาตรฐาน (Street Map)", legend_stats_dict=None):
    """Renders complete Leaflet map HTML with multi-unit interactive carousel popups, genuine company logo markers, layer switcher, and dynamic legend."""
    logo_dict = get_leaflet_logo_dict()
    props_json = json.dumps(nearby_props, ensure_ascii=False).replace("</script>", "<\\/script>")
    logos_json = json.dumps(logo_dict, ensure_ascii=False).replace("</script>", "<\\/script>")
    legend_stats_json = json.dumps(legend_stats_dict or {}, ensure_ascii=False).replace("</script>", "<\\/script>")
    
    if "ดาวเทียม" in tile_style or "satellite" in tile_style.lower():
        default_base = "satellite"
    elif "มืด" in tile_style or "dark" in tile_style.lower():
        default_base = "dark"
    elif "สว่าง" in tile_style or "light" in tile_style.lower():
        default_base = "light"
    else:
        default_base = "street"
        
    if "ประเภททรัพย์" in color_mode:
        active_color_mode_code = "property_type"
    elif "ราคา" in color_mode:
        active_color_mode_code = "price_level"
    else:
        active_color_mode_code = "company"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap');
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #map {{
                width: 100%;
                height: 100vh;
                min-height: 1100px;
                margin: 0;
                padding: 0;
                font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {'#0f172a' if is_dark_mode else '#f8fafc'};
                border-radius: 14px;
            }}
            .logo-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 34px;
                height: 34px;
                background: #ffffff;
                border-radius: 50%;
                border: 2.5px solid #3b82f6;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                cursor: pointer;
                overflow: visible;
                box-sizing: border-box;
                padding: 0;
                position: relative;
            }}
            .logo-marker-pin:hover {{
                transform: scale(1.25);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
                z-index: 1000 !important;
            }}
            .logo-marker-pin img {{
                width: 22px;
                height: 22px;
                max-width: 22px;
                max-height: 22px;
                object-fit: contain;
                display: block;
                margin: 0 auto;
                border-radius: 4px;
            }}
            .cluster-badge-count {{
                position: absolute;
                top: -7px;
                right: -7px;
                background: #059669;
                color: #ffffff;
                font-size: 11px;
                font-weight: 800;
                padding: 1.5px 6px;
                border-radius: 12px;
                border: 1.5px solid #ffffff;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
                line-height: 1.1;
                white-space: nowrap !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                z-index: 1000 !important;
            }}
            .centroid-badge {{
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
                color: #ffffff !important;
                border-color: #ffffff !important;
                font-weight: 900 !important;
                box-shadow: 0 2px 8px rgba(217, 119, 6, 0.6) !important;
                white-space: nowrap !important;
            }}
            .type-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                border: 2px solid #ffffff;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.35);
                transition: transform 0.2s ease;
                cursor: pointer;
                font-size: 15px;
                box-sizing: border-box;
                color: #ffffff;
            }}
            .type-marker-pin:hover {{
                transform: scale(1.35);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
                z-index: 1000 !important;
            }}
            .cluster-marker-pin {{
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                width: 42px;
                height: 42px;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border-radius: 50%;
                border: 2.5px solid #38bdf8;
                box-shadow: 0 4px 16px rgba(56, 189, 248, 0.5);
                cursor: pointer;
                transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.25s ease, border-color 0.2s ease;
                box-sizing: border-box;
                position: relative;
            }}
            .cluster-marker-pin:hover {{
                transform: scale(1.25);
                box-shadow: 0 8px 25px rgba(56, 189, 248, 0.85);
                border-color: #ffffff;
                z-index: 1000 !important;
            }}
            .cluster-marker-count {{
                font-size: 14px;
                font-weight: 900;
                color: #ffffff;
                line-height: 1;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
            }}
            .cluster-marker-sub {{
                font-size: 8px;
                font-weight: 700;
                color: #38bdf8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-top: 1px;
            }}
            .ref-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 44px;
                height: 44px;
                background: #ef4444;
                border-radius: 50%;
                border: 3.5px solid #ffffff;
                box-shadow: 0 4px 16px rgba(239, 68, 68, 0.65);
                animation: pulse-ring 2s infinite;
                box-sizing: border-box;
            }}
            .ref-marker-pin-inner {{
                width: 16px;
                height: 16px;
                background: #ffffff;
                border-radius: 50%;
                box-shadow: 0 1px 4px rgba(0,0,0,0.35);
            }}
            @keyframes pulse-ring {{
                0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
                70% {{ box-shadow: 0 0 0 18px rgba(239, 68, 68, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
            }}
            .leaflet-popup-content-wrapper {{
                background: #ffffff !important;
                color: #0f172a !important;
                border-radius: 16px !important;
                border: 1px solid rgba(0, 0, 0, 0.12) !important;
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.22) !important;
                padding: 4px !important;
            }}
            .leaflet-popup-tip {{
                background: #ffffff !important;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.14) !important;
            }}
            .leaflet-popup-content {{
                margin: 12px 14px !important;
                line-height: 1.45 !important;
                color: #0f172a !important;
            }}
            .leaflet-tooltip {{
                background: rgba(15, 23, 42, 0.94) !important;
                color: #ffffff !important;
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.18) !important;
                box-shadow: 0 6px 18px rgba(0,0,0,0.3) !important;
                padding: 6px 10px !important;
                font-size: 12.5px !important;
            }}
            .multi-pill-scroll {{
                display: flex;
                gap: 6px;
                overflow-x: auto;
                padding: 3px 2px 7px 2px;
                margin-bottom: 9px;
                scrollbar-width: thin;
                scrollbar-color: #cbd5e1 transparent;
                scroll-behavior: smooth;
            }}
            .multi-pill-tab {{
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                color: #334155;
                border-radius: 16px;
                padding: 5px 11px;
                font-size: 12.5px;
                cursor: pointer;
                white-space: nowrap;
                transition: all 0.15s ease;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
                font-weight: 600;
                outline: none;
            }}
            .multi-pill-tab.active {{
                background: #059669;
                color: #ffffff;
                border-color: #047857;
                font-weight: 800;
                box-shadow: 0 3px 10px rgba(5, 150, 105, 0.4);
            }}
            .unit-nav-btn {{
                background: #ffffff;
                border: 1px solid #cbd5e1;
                color: #047857;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                font-size: 10px;
                padding: 0;
                transition: all 0.15s ease;
                box-shadow: 0 1px 2px rgba(0,0,0,0.06);
            }}
            .unit-nav-btn:hover {{
                background: #ecfdf5;
                border-color: #059669;
                color: #047857;
                transform: scale(1.12);
            }}
            .unit-nav-bar-btn {{
                background: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12.5px;
                font-weight: 700;
                color: #1e293b;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.06);
                transition: all 0.15s ease;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
            }}
            .view-toggle-btn {{
                display: block;
                width: 100%;
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                color: #1e293b;
                border-radius: 9px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 700;
                text-align: center;
                cursor: pointer;
                margin-top: 9px;
                transition: all 0.15s ease;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
            }}
            .map-legend-box {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 0, 0, 0.1);
                color: #0f172a;
                padding: 10px 14px;
                border-radius: 12px;
                font-size: 11.5px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);
                max-height: 240px;
                overflow-y: auto;
                line-height: 1.5;
            }}
            .map-legend-title {{
                font-weight: 800;
                font-size: 12px;
                margin-bottom: 6px;
                color: #1e293b;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: 4px;
            }}
            .map-legend-item {{
                display: flex;
                align-items: center;
                gap: 7px;
                margin-bottom: 3px;
                color: #334155;
            }}
            .map-legend-color {{
                width: 13px;
                height: 13px;
                border-radius: 50%;
                border: 1.5px solid #ffffff;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                flex-shrink: 0;
            }}
            .leaflet-control-layers {{
                background: rgba(255, 255, 255, 0.95) !important;
                backdrop-filter: blur(10px) !important;
                border: 1px solid rgba(0, 0, 0, 0.1) !important;
                color: #0f172a !important;
                border-radius: 10px !important;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif !important;
                font-size: 12px !important;
                box-shadow: 0 4px 16px rgba(0,0,0,0.12) !important;
            }}
            .leaflet-control-layers-base label {{
                color: #1e293b !important;
                margin-bottom: 3px !important;
                cursor: pointer !important;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map', {{
                zoomControl: true,
                attributionControl: false,
                dragging: true,
                touchZoom: true,
                scrollWheelZoom: true,
                doubleClickZoom: true,
                boxZoom: true,
                keyboard: true
            }}).setView([{inp_lat}, {inp_lng}], 13);

            var streetLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var osmLayer = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }});
            var satLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var topoLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var darkLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ maxZoom: 19 }});

            var defaultBaseKey = "{default_base}";
            if (defaultBaseKey === "satellite") {{
                satLayer.addTo(map);
            }} else if (defaultBaseKey === "dark") {{
                darkLayer.addTo(map);
            }} else if (defaultBaseKey === "osm") {{
                osmLayer.addTo(map);
            }} else {{
                streetLayer.addTo(map);
            }}

            var baseMaps = {{
                "แผนที่ถนนมาตรฐาน (Esri Street)": streetLayer,
                "OpenStreetMap": osmLayer,
                "ภาพถ่ายดาวเทียม (Satellite)": satLayer,
                "ภูมิประเทศ (Topographic)": topoLayer,
                "โหมดมืด (Dark Canvas)": darkLayer
            }};
            L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

            var logos = {logos_json};
            var properties = {props_json};
            var colorMode = "{active_color_mode_code}";
            var legendStats = {legend_stats_json};

            var companyColors = {{
                "LED": "#0891b2", "SAM": "#10b981", "BAM": "#3b82f6", "Chayo555": "#f97316", "Chayo": "#f97316",
                "GHB": "#ca8a04", "KBANK": "#059669", "KTB": "#0284c7", "SCB": "#7e22ce", "GSB": "#eb1985",
                "DDproperty": "#a855f7", "Livinginsider": "#14b8a6", "NaYoo": "#8b5cf6", "ZmyHome": "#ec4899", "Baania": "#f59e0b"
            }};

            var propTypeColors = {{
                "บ้านเดี่ยว": "#059669", "ห้องชุดพักอาศัย": "#2563eb", "คอนโด": "#2563eb", "คอนโดมิเนียม": "#2563eb",
                "ทาวน์เฮ้าส์": "#f59e0b", "ทาวน์โฮม": "#f59e0b", "ที่ดินเปล่า": "#10b981", "ที่ดิน": "#10b981",
                "ที่ดินพร้อมสิ่งปลูกสร้าง": "#f97316",
                "อาคารพาณิชย์": "#7c3aed", "โรงงาน/โกดัง": "#d97706", "อพาร์ทเมนท์": "#db2777", "บ้านแฝด": "#0284c7"
            }};
            var propTypeIcons = {{
                "บ้านเดี่ยว": '<i class="fa-solid fa-house" style="color:#ffffff; font-size:13px;"></i>',
                "ห้องชุดพักอาศัย": '<i class="fa-solid fa-building" style="color:#ffffff; font-size:13px;"></i>',
                "คอนโด": '<i class="fa-solid fa-building" style="color:#ffffff; font-size:13px;"></i>',
                "คอนโดมิเนียม": '<i class="fa-solid fa-building" style="color:#ffffff; font-size:13px;"></i>',
                "ทาวน์เฮ้าส์": '<i class="fa-solid fa-city" style="color:#ffffff; font-size:13px;"></i>',
                "ทาวน์โฮม": '<i class="fa-solid fa-city" style="color:#ffffff; font-size:13px;"></i>',
                "ที่ดินเปล่า": '<i class="fa-solid fa-tree" style="color:#ffffff; font-size:13px;"></i>',
                "ที่ดิน": '<i class="fa-solid fa-tree" style="color:#ffffff; font-size:13px;"></i>',
                "ที่ดินพร้อมสิ่งปลูกสร้าง": '<i class="fa-solid fa-tree-city" style="color:#ffffff; font-size:13px;"></i>',
                "อาคารพาณิชย์": '<i class="fa-solid fa-store" style="color:#ffffff; font-size:13px;"></i>',
                "โรงงาน/โกดัง": '<i class="fa-solid fa-industry" style="color:#ffffff; font-size:13px;"></i>',
                "อพาร์ทเมนท์": '<i class="fa-solid fa-hotel" style="color:#ffffff; font-size:13px;"></i>',
                "บ้านแฝด": '<i class="fa-solid fa-house-chimney-window" style="color:#ffffff; font-size:13px;"></i>'
            }};

            function getPriceColor(priceNum) {{
                if (!priceNum || priceNum <= 0) return "#64748b";
                if (priceNum < 1000000) return "#10b981";
                if (priceNum < 3000000) return "#06b6d4";
                if (priceNum < 5000000) return "#3b82f6";
                if (priceNum < 10000000) return "#f59e0b";
                if (priceNum < 20000000) return "#f97316";
                return "#ef4444";
            }}

            function parseRawPrice(priceStr) {{
                if (!priceStr) return 0;
                var num = parseFloat(priceStr.toString().replace(/[^0-9.]/g, ''));
                return isNaN(num) ? 0 : num;
            }}

            var radiusCircle = L.circle([{inp_lat}, {inp_lng}], {{
                radius: {search_radius_km * 1000},
                color: '#6366f1',
                fillColor: '#6366f1',
                fillOpacity: 0.12,
                weight: 2.5,
                dashArray: '6, 6'
            }}).addTo(map);

            var refIcon = L.divIcon({{
                className: 'custom-ref-icon',
                html: '<div class="ref-marker-pin"><div class="ref-marker-pin-inner"></div></div>',
                iconSize: [44, 44],
                iconAnchor: [22, 22]
            }});

            var refMarker = L.marker([{inp_lat}, {inp_lng}], {{ icon: refIcon }}).addTo(map);
            refMarker.bindPopup('<div style="font-size:13.5px; font-weight:800; color:#ef4444; margin-bottom:3px;">จุดอ้างอิงของคุณ</div><div style="font-size:12px; color:#64748b;">ศูนย์กลางการค้นหารัศมี ({search_radius_km} กม.)</div><div style="font-size:11px; color:#475569; margin-top:3px;">พิกัด: {inp_lat:.5f}, {inp_lng:.5f}</div>');
            refMarker.bindTooltip('จุดอ้างอิง ({search_radius_km} กม.)', {{ direction: 'top', offset: [0, -22] }});

            window.copyTextVal = function(btn, text, successMsg) {{
                if (!text) return;
                var showFeedback = function() {{
                    if (!btn) return;
                    var oldHtml = btn.innerHTML;
                    btn.innerHTML = successMsg || '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกแล้ว!';
                    btn.style.borderColor = '#10b981';
                    btn.style.color = '#059669';
                    setTimeout(function() {{
                        btn.innerHTML = oldHtml;
                        btn.style.borderColor = '';
                        btn.style.color = '';
                    }}, 2000);
                }};

                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(text).then(function() {{
                        showFeedback();
                    }})['catch'](function() {{
                        fallbackCopy();
                    }});
                }} else {{
                    fallbackCopy();
                }}

                function fallbackCopy() {{
                    try {{
                        var ta = document.createElement('textarea');
                        ta.value = text;
                        ta.style.position = 'fixed';
                        ta.style.opacity = '0';
                        document.body.appendChild(ta);
                        ta.focus();
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                        showFeedback();
                    }} catch(e) {{}}
                }}
            }};

            window.copyCoordBtn = function(btn) {{
                var c = btn.getAttribute('data-coord') || '';
                window.copyTextVal(btn, c, '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกพิกัดแล้ว!');
            }};

            window.copyCodeBtn = function(btn) {{
                var c = btn.getAttribute('data-code') || '';
                window.copyTextVal(btn, c, '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกรหัสแล้ว!');
            }};

            function getCompanyLogo(comp) {{
                if (!comp || !logos || typeof logos !== 'object') return '';
                var c = String(comp).trim();
                if (logos[c]) return logos[c];
                if (logos[c.toLowerCase()]) return logos[c.toLowerCase()];
                if (logos[c.toUpperCase()]) return logos[c.toUpperCase()];
                var cLower = c.toLowerCase();
                for (var k in logos) {{
                    var kLower = k.toLowerCase();
                    if (cLower === kLower || cLower.indexOf(kLower) !== -1 || kLower.indexOf(cLower) !== -1) {{
                        return logos[k];
                    }}
                }}
                return '';
            }}

            function createPropertyIcon(p, isCentroid) {{
                var comp = p.company || 'BAM';
                var pType = p.type || 'อื่นๆ';
                var rawP = parseRawPrice(p.price);
                var compColor = companyColors[comp] || '#2563eb';
                var typeColor = propTypeColors[pType] || '#64748b';
                var priceColor = getPriceColor(rawP);
                var isApprox = Boolean(isCentroid || p.is_centroid);
                var approxBadge = isApprox ? '<span class="cluster-badge-count centroid-badge" style="position:absolute; top:-7px; right:-7px; background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color:#ffffff; font-size:10px; font-weight:900; padding:1px 5px; border-radius:10px; border:1.5px solid #ffffff; box-shadow:0 2px 6px rgba(0,0,0,0.3); z-index:10; white-space:nowrap !important;">!</span>' : '';
                var borderColor = isApprox ? '#f59e0b' : compColor;

                if (colorMode === "property_type") {{
                    var iconEmoji = propTypeIcons[pType] || '<i class="fa-solid fa-location-dot" style="color:#ffffff; font-size:13px;"></i>';
                    return L.divIcon({{
                        className: 'custom-type-icon',
                        html: '<div class="type-marker-pin" style="background:' + typeColor + '; position:relative;">' + iconEmoji + approxBadge + '</div>',
                        iconSize: [32, 32],
                        iconAnchor: [16, 16],
                        popupAnchor: [0, -16]
                    }});
                }} else if (colorMode === "price_level") {{
                    return L.divIcon({{
                        className: 'custom-price-icon',
                        html: '<div class="type-marker-pin" style="background:' + priceColor + '; font-size:12px; font-weight:800; position:relative;">฿' + approxBadge + '</div>',
                        iconSize: [32, 32],
                        iconAnchor: [16, 16],
                        popupAnchor: [0, -16]
                    }});
                }} else {{
                    var logoUrl = getCompanyLogo(comp);
                    var logoHtml = logoUrl ? '<img src="' + logoUrl + '" alt="' + comp + '" />' : '<span style="font-weight:800; font-size:11px; color:#0f172a;">' + comp.substring(0,3) + '</span>';
                    return L.divIcon({{
                        className: 'custom-logo-icon',
                        html: '<div class="logo-marker-pin" style="border-color:' + borderColor + '; position:relative;">' + logoHtml + approxBadge + '</div>',
                        iconSize: [36, 36],
                        iconAnchor: [18, 18],
                        popupAnchor: [0, -18]
                    }});
                }}
            }}

            function buildItemDetailHTML(p, idxInGroup, totalInGroup, groupKey) {{
                groupKey = groupKey || '';
                var comp = p.company || 'BAM';
                var isLED = (comp === 'LED' || String(comp).toUpperCase().indexOf('LED') !== -1 || String(comp).indexOf('กรมบังคับคดี') !== -1);
                var locParts = [p.subdist, p.district, p.province].filter(function(v) {{
                    return v && v !== 'nan' && v !== 'None' && v !== '-' && String(v).trim() !== '';
                }});
                var locStr = locParts.join(', ');
                var compColor = companyColors[comp] || '#2563eb';
                var logoUrl = getCompanyLogo(comp);
                var logoImg = logoUrl ? '<img src="' + logoUrl + '" style="width:16px;height:16px;object-fit:contain;vertical-align:middle;margin-right:5px;border-radius:3px;" />' : '';

                var validProject = (p.project && p.project !== '-' && p.project !== 'nan') ? p.project : '';
                var landStr = (p.land_area && p.land_area !== '-' && p.land_area !== 'nan') ? p.land_area : '-';
                var usableStr = (p.usable_area && p.usable_area !== '-' && p.usable_area !== 'nan') ? p.usable_area : '-';
                var pricePerWah = (p.price_per_wah && p.price_per_wah !== '-' && p.price_per_wah !== 'nan') ? p.price_per_wah : '';
                var pricePerSqm = (p.price_per_sqm && p.price_per_sqm !== '-' && p.price_per_sqm !== 'nan') ? p.price_per_sqm : '';

                var linksHTML = '';
                if (isLED) {{
                    var pLinkHtml = (p.link && p.link !== '-' && p.link !== '') ? '<a href="' + p.link + '" target="_blank" style="flex:1; text-align:center; background:linear-gradient(135deg, #059669 0%, #047857 100%); color:#ffffff; padding:9px 10px; border-radius:9px; text-decoration:none; font-size:13px; font-weight:800; box-shadow:0 3px 10px rgba(5,150,105,0.3); transition:all 0.15s ease; white-space:nowrap;"><i class="fa-solid fa-arrow-up-right-from-square"></i> เปิดดูประกาศ ↗</a>' : '';
                    linksHTML = '<div style="display:flex; gap:6px; margin-bottom:6px;">' +
                        pLinkHtml +
                        '<a href="https://landsmaps.dol.go.th/" target="_blank" style="flex:1; text-align:center; background:linear-gradient(135deg, #0d9488 0%, #0f766e 100%); color:#ffffff; padding:9px 10px; border-radius:9px; text-decoration:none; font-size:13px; font-weight:800; box-shadow:0 3px 10px rgba(13,148,136,0.3); transition:all 0.15s ease; white-space:nowrap;"><i class="fa-solid fa-map-location-dot"></i> ดูแปลงที่ดิน (LandsMaps) ↗</a>' +
                        '</div>';
                }} else if (p.link && p.link !== '-' && p.link !== '') {{
                    linksHTML = '<a href="' + p.link + '" target="_blank" style="display:block; text-align:center; background:linear-gradient(135deg, #059669 0%, #047857 100%); color:#ffffff; padding:9px 14px; border-radius:9px; text-decoration:none; font-size:13.5px; font-weight:800; box-shadow:0 3px 10px rgba(5,150,105,0.3); margin-bottom:6px; transition:all 0.15s ease;"><i class="fa-solid fa-arrow-up-right-from-square"></i> เปิดดูประกาศทรัพย์สิน ↗</a>';
                }}

                return '<div class="item-card-inner" style="padding: 2px 0;">' +
                    (p.is_centroid ? '<div style="background:#fffbeb; border:1.5px solid #fde68a; border-radius:8px; padding:5px 9px; margin-bottom:8px; font-size:12px; color:#b45309; font-weight:700; display:flex; align-items:center; gap:5px;"><i class="fa-solid fa-triangle-exclamation"></i> <span><b>พิกัดโดยประมาณ</b> (คำนวณจากจุดกึ่งกลางตำบล/อำเภอ)</span></div>' : '') +
                    '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">' +
                    '  <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">' +
                    '    <span style="background:#f8fafc; border-left:4px solid ' + compColor + '; border-top:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; color:#0f172a; padding:3px 9px; border-radius:6px; font-size:13px; font-weight:800;">' + logoImg + comp + '</span>' +
                    '    <span style="background:#fef3c7; border:1px solid #fde68a; color:#92400e; padding:3px 8px; border-radius:6px; font-size:12.5px; font-weight:700;">' + (p.type || '-') + '</span>' +
                    (p.sale_type && p.sale_type !== '-' && p.sale_type !== 'nan' ? '<span style="background:#f1f5f9; color:#334155; padding:3px 7px; border-radius:6px; font-size:12px; font-weight:600;">' + p.sale_type + '</span>' : '') +
                    '  </div>' +
                    (totalInGroup > 1 ?
                        '<div style="display:inline-flex; align-items:center; gap:2px; background:#ecfdf5; border:1.5px solid #a7f3d0; border-radius:14px; padding:2px 4px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">' +
                        '  <button type="button" class="unit-nav-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, -1, ' + totalInGroup + ')" title="ดูทรัพย์ก่อนหน้า"><i class="fa-solid fa-chevron-left"></i></button>' +
                        '  <span style="font-weight:800; font-size:12px; color:#047857; min-width:30px; text-align:center; padding:0 2px;">' + (idxInGroup + 1) + '/' + totalInGroup + '</span>' +
                        '  <button type="button" class="unit-nav-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, 1, ' + totalInGroup + ')" title="ดูทรัพย์ถัดไป"><i class="fa-solid fa-chevron-right"></i></button>' +
                        '</div>' : '') +
                    '</div>' +
                    '<div style="font-weight:800; font-size:15.5px; color:#0f172a; line-height:1.4; margin-bottom:6px; word-break:break-word;">' + (p.name || 'ทรัพย์สิน') + '</div>' +
                    '<div style="color:#475569; font-size:12.5px; margin-bottom:10px;">' +
                    '<i class="fa-solid fa-hashtag" style="color:#64748b; font-size:11px;"></i> รหัส: <b style="color:#0f172a; font-size:13px;">' + (p.code || '-') + '</b>' +
                    (validProject ? ' • <i class="fa-solid fa-building" style="color:#64748b; font-size:11px;"></i> <span style="color:#1e293b; font-weight:600;">' + validProject + '</span>' : '') +
                    '</div>' +
                    '<div style="background:linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border:1.5px solid #86efac; border-radius:10px; padding:9px 12px; margin-bottom:10px;">' +
                    '  <div style="display:flex; justify-content:space-between; align-items:center;">' +
                    '    <div><span style="font-size:11px; color:#166534; text-transform:uppercase; font-weight:800; letter-spacing:0.3px;">ราคาเสนอขาย</span><br/><b style="font-size:21px; color:#15803d; font-family:Noto Sans Thai,Inter,sans-serif; letter-spacing:0.3px; font-weight:900;">' + (p.price || '-') + '</b></div>' +
                    (p.dist ? '<div style="text-align:right;"><span style="font-size:11px; color:#9f1239; font-weight:800;">ระยะห่าง</span><br/><b style="font-size:15px; color:#be123c; font-family:Noto Sans Thai,Inter,sans-serif; font-weight:800;">' + p.dist + '</b></div>' : '') +
                    '  </div>' +
                    '</div>' +
                    '<div style="background:#f8fafc; border-radius:10px; padding:8px 11px; font-size:13px; margin-bottom:10px; border:1px solid #e2e8f0; color:#334155;">' +
                    '  <div style="display:flex; justify-content:space-between; margin-bottom:4px;">' +
                    '    <span><i class="fa-solid fa-ruler-combined" style="color:#64748b; margin-right:3px; font-size:11px;"></i>เนื้อที่: <b style="color:#0f172a;">' + landStr + '</b></span>' +
                    (pricePerWah ? '<span style="color:#059669; font-weight:800;">(' + pricePerWah + ')</span>' : '') +
                    '  </div>' +
                    '  <div style="display:flex; justify-content:space-between;">' +
                    '    <span><i class="fa-solid fa-house-chimney" style="color:#64748b; margin-right:3px; font-size:11px;"></i>ใช้สอย: <b style="color:#0f172a;">' + usableStr + '</b></span>' +
                    (pricePerSqm ? '<span style="color:#059669; font-weight:800;">(' + pricePerSqm + ')</span>' : '') +
                    '  </div>' +
                    '</div>' +
                    (locStr ? '<div style="font-size:12.5px; color:#475569; margin-bottom:10px; line-height:1.4;"><i class="fa-solid fa-location-dot" style="color:#64748b; margin-right:4px;"></i><span style="color:#1e293b; font-weight:500;">' + locStr + '</span></div>' : '') +
                    linksHTML +
                    (totalInGroup === 1 ? '<div style="display:flex; gap:6px; margin-top:8px;">' +
                    '  <button type="button" data-coord="' + parseFloat(p.lat || 0).toFixed(5) + ',' + parseFloat(p.lon || 0).toFixed(5) + '" onclick="window.copyCoordBtn(this)" style="flex:1; background:#f8fafc; border:1.5px solid #cbd5e1; color:#334155; padding:8px 10px; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:all 0.15s ease;"><i class="fa-regular fa-copy"></i> คัดลอกพิกัด</button>' +
                    '  <button type="button" data-code="' + (p.code || p.id || '') + '" onclick="window.copyCodeBtn(this)" style="flex:1; background:#f8fafc; border:1.5px solid #cbd5e1; color:#334155; padding:8px 10px; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:all 0.15s ease;"><i class="fa-regular fa-copy"></i> คัดลอกรหัสทรัพย์</button>' +
                    '</div>' : '') +
                    '</div>';
            }}

            function buildMultiUnitPopupHTML(group) {{
                var total = group.items.length;
                var groupKey = group.key;
                var companiesInGroup = [];
                var allCodesList = [];
                group.items.forEach(function(item) {{
                    if (item.company && companiesInGroup.indexOf(item.company) === -1) {{
                        companiesInGroup.push(item.company);
                    }}
                    var c = item.code || item.id;
                    if (c && c !== '-' && allCodesList.indexOf(c) === -1) {{
                        allCodesList.push(c);
                    }}
                }});

                var grpLatStr = parseFloat(group.lat).toFixed(5);
                var grpLonStr = parseFloat(group.lon).toFixed(5);

                var maxTabs = Math.min(total, 50);
                var tabsHTML = '<div class="multi-pill-scroll" id="pills_' + groupKey + '">';
                var cardsHTML = '<div id="card_view_' + groupKey + '">';
                var tableRowsHTML = '';

                group.items.forEach(function(item, i) {{
                    var comp = item.company || 'BAM';
                    var cColor = companyColors[comp] || '#64748b';
                    var activeClass = i === 0 ? 'active' : '';
                    var activeDisplay = i === 0 ? 'block' : 'none';
                    var itemLogo = getCompanyLogo(comp);
                    var pillLogo = itemLogo ? '<img src="' + itemLogo + '" style="width:15px;height:15px;object-fit:contain;vertical-align:middle;margin-right:4px;border-radius:2px;" />' : '';

                    var itemUnitTag = item.price_per_wah || item.price_per_sqm || '';
                    var itemUnitHtml = itemUnitTag ? ' <span style="font-size:10px; color:#059669; font-weight:700;">(' + itemUnitTag + ')</span>' : '';
                    if (i < maxTabs) {{
                        tabsHTML += '<button type="button" class="multi-pill-tab ' + activeClass + '" data-group="' + groupKey + '" data-idx="' + i + '" onclick="window.switchMultiUnitTab(this.dataset.group, parseInt(this.dataset.idx))" id="tab_' + groupKey + '_' + i + '" style="border-left:3.5px solid ' + cColor + ';">' +
                            pillLogo + (i + 1) + '. ' + comp + ' ' + (item.price || '-') + itemUnitHtml +
                            '</button>';
                    }}

                    cardsHTML += '<div class="unit-slide" id="slide_' + groupKey + '_' + i + '" style="display:' + activeDisplay + ';">' +
                        buildItemDetailHTML(item, i, total, groupKey) +
                        '</div>';

                    if (i < 25) {{
                        var landOrUse = (item.land_area && item.land_area !== '-' && item.land_area !== 'nan') ? item.land_area : (item.usable_area || '-');
                        var rowLogo = getCompanyLogo(comp);
                        var rowLogoImg = rowLogo ? '<img src="' + rowLogo + '" style="width:15px;height:15px;object-fit:contain;vertical-align:middle;margin-right:4px;border-radius:2px;" />' : '';
                        var rowCode = item.code || item.id || '';
                        var isRowLED = (comp === 'LED' || String(comp).toUpperCase().indexOf('LED') !== -1 || String(comp).indexOf('กรมบังคับคดี') !== -1);
                        tableRowsHTML += '<tr style="border-bottom:1px solid #f1f5f9;">' +
                            '<td style="padding:6px 8px; font-weight:700; color:' + cColor + '; white-space:nowrap;">' + rowLogoImg + comp + '</td>' +
                            '<td style="padding:6px 8px; color:#0f172a; font-weight:600;">' + (item.code || '-') + '</td>' +
                            '<td style="padding:6px 8px; font-weight:800; color:#15803d;">' + (item.price || '-') + '</td>' +
                            '<td style="padding:6px 8px; color:#475569;">' + landOrUse + '</td>' +
                            '<td style="padding:6px 8px; text-align:right; white-space:nowrap;">' +
                            (item.link ? '<a href="' + item.link + '" target="_blank" style="color:#2563eb; text-decoration:none; font-weight:700; margin-right:6px;" title="เปิดดูประกาศ"><i class="fa-solid fa-arrow-up-right-from-square"></i> ดู</a>' : '') +
                            (isRowLED ? '<a href="https://landsmaps.dol.go.th/" target="_blank" style="color:#0d9488; text-decoration:none; font-weight:700; margin-right:6px;" title="ระบบค้นหารูปแปลงที่ดิน (LandsMaps)"><i class="fa-solid fa-map-location-dot"></i> แปลง LandsMaps</a>' : '') +
                            '<button type="button" data-code="' + rowCode + '" onclick="window.copyCodeBtn(this)" style="background:#f8fafc; border:1px solid #cbd5e1; color:#475569; padding:3px 7px; border-radius:5px; font-size:11px; font-weight:700; cursor:pointer; display:inline-block;"><i class="fa-regular fa-copy"></i> คัดลอก</button>' +
                            '</td>' +
                            '</tr>';
                    }}
                }});

                if (total > maxTabs) {{
                    tabsHTML += '<span style="font-size:11.5px; font-weight:700; color:#64748b; align-self:center; white-space:nowrap; padding:0 6px;">+' + (total - maxTabs) + '</span>';
                }}

                tabsHTML += '</div>';
                cardsHTML += '</div>';

                var navBarHTML = '';
                if (total > 1) {{
                    navBarHTML = '<div id="nav_bar_' + groupKey + '" class="multi-unit-nav-bar" style="display:flex; justify-content:space-between; align-items:center; background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:10px; padding:6px 10px; margin-top:8px; margin-bottom:6px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">' +
                        '  <button type="button" class="unit-nav-bar-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, -1, ' + total + ')" title="ดูทรัพย์ก่อนหน้า"><i class="fa-solid fa-chevron-left" style="color:#059669;"></i> ก่อนหน้า</button>' +
                        '  <div style="display:flex; flex-direction:column; align-items:center; line-height:1.2;">' +
                        '    <span style="font-size:10.5px; color:#64748b; font-weight:700;">เลื่อนดูทรัพย์</span>' +
                        '    <b id="nav_counter_' + groupKey + '" style="font-size:13.5px; color:#059669; font-weight:900;">1 / ' + total + '</b>' +
                        '  </div>' +
                        '  <button type="button" class="unit-nav-bar-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, 1, ' + total + ')" title="ดูทรัพย์ถัดไป">ถัดไป <i class="fa-solid fa-chevron-right" style="color:#059669;"></i></button>' +
                        '</div>';
                }}

                var compareTableHTML = '<div id="table_view_' + groupKey + '" style="display:none; margin-top:6px;">' +
                    '<div style="max-height:180px; overflow-y:auto; background:#ffffff; border-radius:9px; border:1px solid #e2e8f0;">' +
                    '<table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">' +
                    '<thead><tr style="background:#f8fafc; color:#475569; border-bottom:1px solid #e2e8f0;"><th style="padding:6px 8px;">บริษัท</th><th style="padding:6px 8px;">รหัส</th><th style="padding:6px 8px;">ราคา</th><th style="padding:6px 8px;">พื้นที่</th><th style="padding:6px 8px; text-align:right;">การกระทำ</th></tr></thead>' +
                    '<tbody>' + tableRowsHTML + '</tbody>' +
                    '</table>' +
                    '</div>' +
                    '</div>';

                var toggleBtnHTML = '<button type="button" class="view-toggle-btn" data-group="' + groupKey + '" data-total="' + total + '" onclick="window.toggleMultiUnitView(this.dataset.group, parseInt(this.dataset.total))" id="btn_toggle_' + groupKey + '"><i class="fa-solid fa-table-list" style="margin-right:4px;"></i>สลับดูตารางเปรียบเทียบยูนิต (' + total + ' รายการ)</button>';

                var totalDisplay = (group.items.length > 0 && group.items[0].coord_total) ? group.items[0].coord_total : total;
                var isGroupCentroid = group.items.some(function(item) {{ return Boolean(item.is_centroid); }});
                var centroidBadgeHeader = isGroupCentroid ? '<span style="background:#fef3c7; border:1px solid #fde68a; color:#92400e; font-size:11.5px; padding:1.5px 7px; border-radius:6px; font-weight:800; margin-left:5px; vertical-align:middle;"><i class="fa-solid fa-triangle-exclamation"></i> พิกัดกึ่งกลาง</span>' : '';

                var mainActionsHTML = '<div style="margin-bottom:10px;">' +
                    '  <button type="button" data-coord="' + grpLatStr + ',' + grpLonStr + '" onclick="window.copyCoordBtn(this)" style="width:100%; background:#f8fafc; border:1.5px solid #cbd5e1; color:#334155; padding:8px 10px; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:all 0.15s ease;"><i class="fa-regular fa-copy"></i> คัดลอกพิกัด</button>' +
                    '</div>';

                return '<div class="multi-unit-popup" style="min-width:340px; max-width:390px;">' +
                    '<div class="multi-popup-header" style="margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid #e2e8f0;">' +
                    '  <div style="font-weight:800; font-size:14.5px; color:#0f172a;"><i class="fa-solid fa-building" style="color:#059669; margin-right:4px;"></i>พิกัดนี้พบ ' + totalDisplay + ' ทรัพย์สิน ' + centroidBadgeHeader + ' <span style="font-weight:500; font-size:12.5px; color:#64748b;">(' + companiesInGroup.join(', ') + ')</span></div>' +
                    '  <div style="font-size:11px; color:#059669; font-weight:700; margin-top:2px;"><i class="fa-solid fa-arrow-down-short-wide" style="margin-right:3px;"></i>เรียงจากราคาเสนอขาย / ราคาต่อหน่วยต่ำสุดขึ้นก่อน</div>' +
                    '</div>' +
                    mainActionsHTML +
                    tabsHTML +
                    cardsHTML +
                    navBarHTML +
                    compareTableHTML +
                    toggleBtnHTML +
                    '</div>';
            }}

            window.switchMultiUnitTab = function(groupKey, targetIdx) {{
                var cardView = document.getElementById('card_view_' + groupKey);
                var tableView = document.getElementById('table_view_' + groupKey);
                var toggleBtn = document.getElementById('btn_toggle_' + groupKey);
                var navBar = document.getElementById('nav_bar_' + groupKey);
                
                if (cardView) cardView.style.display = 'block';
                if (tableView) tableView.style.display = 'none';
                if (navBar) navBar.style.display = 'flex';
                if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-table-list" style="margin-right:4px;"></i>สลับดูตารางเปรียบเทียบทุกยูนิต';

                var tabs = document.querySelectorAll('[id^="tab_' + groupKey + '_"]');
                tabs.forEach(function(t) {{ t.classList.remove('active'); }});
                
                var slides = document.querySelectorAll('[id^="slide_' + groupKey + '_"]');
                slides.forEach(function(s) {{ s.style.display = 'none'; }});
                
                var targetTab = document.getElementById('tab_' + groupKey + '_' + targetIdx);
                if (targetTab) {{
                    targetTab.classList.add('active');
                    try {{
                        targetTab.scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
                    }} catch(e) {{}}
                }}
                
                var targetSlide = document.getElementById('slide_' + groupKey + '_' + targetIdx);
                if (targetSlide) targetSlide.style.display = 'block';

                var counterEl = document.getElementById('nav_counter_' + groupKey);
                if (counterEl) {{
                    var total = slides.length;
                    counterEl.textContent = (targetIdx + 1) + ' / ' + total;
                }}
            }};

            window.stepMultiUnitSlide = function(groupKey, delta, total) {{
                var currentIdx = 0;
                var activeTab = document.querySelector('[id^="tab_' + groupKey + '_"].active');
                if (activeTab && activeTab.dataset.idx !== undefined) {{
                    currentIdx = parseInt(activeTab.dataset.idx, 10);
                }}
                var nextIdx = currentIdx + delta;
                if (nextIdx < 0) {{
                    nextIdx = total - 1;
                }} else if (nextIdx >= total) {{
                    nextIdx = 0;
                }}
                window.switchMultiUnitTab(groupKey, nextIdx);
            }};

            window.toggleMultiUnitView = function(groupKey, total) {{
                var cardView = document.getElementById('card_view_' + groupKey);
                var tableView = document.getElementById('table_view_' + groupKey);
                var toggleBtn = document.getElementById('btn_toggle_' + groupKey);
                var navBar = document.getElementById('nav_bar_' + groupKey);
                if (!cardView || !tableView) return;

                if (tableView.style.display === 'none' || tableView.style.display === '') {{
                    cardView.style.display = 'none';
                    tableView.style.display = 'block';
                    if (navBar) navBar.style.display = 'none';
                    if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-regular fa-id-card" style="margin-right:4px;"></i>สลับกลับมาดูการ์ดรายยูนิต';
                }} else {{
                    cardView.style.display = 'block';
                    tableView.style.display = 'none';
                    if (navBar) navBar.style.display = 'flex';
                    if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-table-list" style="margin-right:4px;"></i>สลับดูตารางเปรียบเทียบยูนิต (' + total + ' รายการ)';
                }}
            }};

            var coordGroups = {{}};
            properties.forEach(function(p) {{
                if (!p.lat || !p.lon) return;
                var key = parseFloat(p.lat).toFixed(5) + '_' + parseFloat(p.lon).toFixed(5);
                if (!coordGroups[key]) {{
                    coordGroups[key] = {{
                        key: key,
                        lat: parseFloat(p.lat),
                        lon: parseFloat(p.lon),
                        items: []
                    }};
                }}
                coordGroups[key].items.push(p);

                var comp = p.company || 'BAM';
                var pType = p.type || 'อื่นๆ';
                var rawP = parseRawPrice(p.price);
                if (colorMode === "property_type") {{
                    legendStats[pType] = (legendStats[pType] || 0) + 1;
                }} else if (colorMode === "price_level") {{
                    var priceTier = rawP < 1000000 ? "< 1M" : (rawP < 3000000 ? "1M - 3M" : (rawP < 5000000 ? "3M - 5M" : (rawP < 10000000 ? "5M - 10M" : (rawP < 20000000 ? "10M - 20M" : "> 20M"))));
                    legendStats[priceTier] = (legendStats[priceTier] || 0) + 1;
                }} else {{
                    legendStats[comp] = (legendStats[comp] || 0) + 1;
                }}
            }});

            for (var grpKey in coordGroups) {{
                coordGroups[grpKey].items.sort(function(a, b) {{
                    var pA = (typeof a.raw_price === 'number' && a.raw_price > 0) ? a.raw_price : parseRawPrice(a.price);
                    var pB = (typeof b.raw_price === 'number' && b.raw_price > 0) ? b.raw_price : parseRawPrice(b.price);
                    var vPA = (pA > 0) ? pA : Infinity;
                    var vPB = (pB > 0) ? pB : Infinity;
                    if (vPA !== vPB) return vPA - vPB;

                    var uA = (typeof a.raw_unit_price === 'number' && a.raw_unit_price > 0) ? a.raw_unit_price : parseRawPrice(a.unit_price || a.price_per_wah || a.price_per_sqm);
                    var uB = (typeof b.raw_unit_price === 'number' && b.raw_unit_price > 0) ? b.raw_unit_price : parseRawPrice(b.unit_price || b.price_per_wah || b.price_per_sqm);
                    var vUA = (uA > 0) ? uA : Infinity;
                    var vUB = (uB > 0) ? uB : Infinity;
                    return vUA - vUB;
                }});
            }}

            for (var k in coordGroups) {{
                (function(group) {{
                    var count = group.items.length;
                    var displayCount = (group.items.length > 0 && group.items[0].coord_total) ? group.items[0].coord_total : count;
                    var isGroupCentroid = group.items.some(function(it) {{ return Boolean(it.is_centroid); }});
                    if (displayCount === 1) {{
                        var p = group.items[0];
                        var markerIcon = createPropertyIcon(p, isGroupCentroid);
                        var marker = L.marker([group.lat, group.lon], {{ icon: markerIcon }}).addTo(map);
                        
                        var popupContent = buildItemDetailHTML(p, 0, 1);
                        marker.bindPopup(popupContent, {{ maxWidth: 390 }});

                        var locStr = [p.subdist, p.district, p.province].filter(Boolean).join(', ');
                        var tooltipContent = '<div style="font-size:12px; line-height:1.4;">' +
                            '<b style="color:#059669;">' + (p.name || 'ทรัพย์สิน') + (isGroupCentroid ? ' (พิกัดกึ่งกลาง)' : '') + '</b><br/>' +
                            '<b>' + (p.company || '-') + '</b> | ' + (p.type || '-') + '<br/>' +
                            '<b style="color:#15803d;">' + (p.price || '-') + '</b> | ' + (p.dist || '-') +
                            (locStr ? '<br/><span style="color:#64748b;">' + locStr + '</span>' : '') +
                            '</div>';
                        marker.bindTooltip(tooltipContent, {{ direction: 'top', offset: [0, -17] }});
                    }} else {{
                        var uniqueComps = [];
                        group.items.forEach(function(item) {{
                            if (item.company && uniqueComps.indexOf(item.company) === -1) {{
                                uniqueComps.push(item.company);
                            }}
                        }});

                        var primaryComp = group.items[0].company || 'SAM';
                        var primaryLogo = getCompanyLogo(primaryComp);
                        var cColor = companyColors[primaryComp] || '#2563eb';
                        var pinBorderColor = isGroupCentroid ? '#f59e0b' : cColor;
                        
                        var logoImgHtml = primaryLogo ? '<img src="' + primaryLogo + '" alt="' + primaryComp + '" />' : '<span style="font-weight:800; font-size:11px; color:#0f172a;">' + primaryComp.substring(0,3) + '</span>';

                        var badgeClass = isGroupCentroid ? 'cluster-badge-count centroid-badge' : 'cluster-badge-count';
                        var badgeStyle = isGroupCentroid ? 'style="background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color:#ffffff; border-color:#ffffff; font-weight:900; box-shadow:0 2px 8px rgba(217,119,6,0.6); white-space:nowrap !important;"' : 'style="white-space:nowrap !important;"';
                        var badgeText = isGroupCentroid ? (displayCount + '<span style="font-weight:900; margin-left:1.5px;">!</span>') : displayCount;

                        var clusterIconHTML = '<div class="logo-marker-pin" style="border-color:' + pinBorderColor + '; width:38px; height:38px;">' +
                            logoImgHtml +
                            '<span class="' + badgeClass + '" ' + badgeStyle + '>' + badgeText + '</span>' +
                            '</div>';

                        var clusterIcon = L.divIcon({{
                            className: 'custom-cluster-icon',
                            html: clusterIconHTML,
                            iconSize: [38, 38],
                            iconAnchor: [19, 19],
                            popupAnchor: [0, -19]
                        }});

                        var clusterMarker = L.marker([group.lat, group.lon], {{ icon: clusterIcon }}).addTo(map);

                        var multiPopupHTML = buildMultiUnitPopupHTML(group);
                        clusterMarker.bindPopup(multiPopupHTML, {{ maxWidth: 410 }});

                        var clusterTooltip = '<div style="font-size:12px; line-height:1.4;">' +
                            '<b style="color:#059669;">พิกัดนี้มี ' + displayCount + ' ทรัพย์สิน' + (isGroupCentroid ? ' (พิกัดกึ่งกลาง)' : '') + '</b><br/>' +
                            'สถาบัน: <b>' + uniqueComps.join(', ') + '</b><br/>' +
                            '<span style="color:#64748b; font-size:10.5px;">คลิกเพื่อดูรายละเอียดและตารางเปรียบเทียบยูนิต</span>' +
                            '</div>';
                        clusterMarker.bindTooltip(clusterTooltip, {{ direction: 'top', offset: [0, -19] }});
                    }}
                }})(coordGroups[k]);
            }}

            var legendControl = L.control({{ position: 'bottomright' }});
            legendControl.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'map-legend-box');
                var titleText = colorMode === "property_type" ? "ประเภททรัพย์" : (colorMode === "price_level" ? "ระดับราคา" : "บริษัททรัพย์สิน");
                var html = '<div class="map-legend-title">' + titleText + ' (พบในรัศมี)</div>';

                var priceColorsMap = {{
                    "< 1M": "#10b981", "1M - 3M": "#06b6d4", "3M - 5M": "#3b82f6",
                    "5M - 10M": "#f59e0b", "10M - 20M": "#f97316", "> 20M": "#ef4444"
                }};

                var customLegendStats = {legend_stats_json};
                var activeStats = (customLegendStats && Object.keys(customLegendStats).length > 0) ? customLegendStats : legendStats;

                for (var key in activeStats) {{
                    var dotColor = "#64748b";
                    if (colorMode === "property_type") {{
                        dotColor = propTypeColors[key] || "#64748b";
                    }} else if (colorMode === "price_level") {{
                        dotColor = priceColorsMap[key] || "#64748b";
                    }} else {{
                        dotColor = companyColors[key] || "#64748b";
                    }}
                    var countVal = activeStats[key];
                    var countFmt = typeof countVal === 'number' ? countVal.toLocaleString() : countVal;
                    html += '<div class="map-legend-item">' +
                        '<span class="map-legend-color" style="background:' + dotColor + ';"></span>' +
                        '<span><b>' + key + '</b> (' + countFmt + ')</span>' +
                        '</div>';
                }}
                div.innerHTML = html;
                return div;
            }};
            legendControl.addTo(map);

            var group = new L.featureGroup([radiusCircle]);
            map.fitBounds(group.getBounds(), {{ padding: [30, 30] }});

            setTimeout(function() {{
                map.invalidateSize();
            }}, 250);
            window.addEventListener('resize', function() {{
                map.invalidateSize();
            }});
        </script>
    </body>
    </html>
    """
    return html
