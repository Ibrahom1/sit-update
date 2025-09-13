import requests
import json
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os
import sys

# Load environment variables from .env file if it exists (for local development)
def load_env_file():
    """Load environment variables from .env file if it exists"""
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except FileNotFoundError:
        pass

# Load .env file for local development
load_env_file()

# === API Configuration ===
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("Error: API_KEY not found in environment variables")
    sys.exit(1)

if not API_URL:
    print("Error: API_URL not found in environment variables")
    sys.exit(1)

# === Constants ===
TIMESTAMP_FILE = "last_reading_time.timestamp"

# Image dimensions
W = 1080  # Width remains fixed
BG = "#FFF9F0"
HEADER_GREEN = "#0A6B46"

# Color mappings
SEVERITY_COLORS = {
    "NORMAL": "#0F8A26",
    "LOW": "#00B5E2",
    "MEDIUM": "#F2B233",
    "HIGH": "#C95E0C",
    "VERY_HIGH": "#FF2222",
    "V_HIGH": "#FF2222",
    "EX_HIGH": "#5A0A0A",
    "EXCEPTIONALLY_HIGH": "#5A0A0A",
    "EXCEPTIONALLY HIGH": "#5A0A0A",
    "VERY HIGH": "#FF2222",
}

SEVERITY_DISPLAY = {
    "NORMAL": "Normal",
    "LOW": "Low",
    "MEDIUM": "Medium",
    "HIGH": "High",
    "VERY_HIGH": "V High",
    "EX_HIGH": "Ex High",
    "EXCEPTIONALLY_HIGH": "Ex High",
    "EXCEPTIONALLY HIGH": "Ex High",
    "VERY HIGH": "V High",
}

TREND_COLORS = {
    "Falling": "#32CD32",
    "Steady": "#008000",
    "Rising": "#E00000",
}

# Station configuration with {rivername} at {headwork} format
STATION_ORDER = [
    # Ravi River stations (0-3)
    {"key": "Jassar", "api_name": "Jassar", "river": "Ravi", "headwork": "Jassar", "short_name": "Jassar"},
    {"key": "Shahdara", "api_name": "Shahdara", "river": "Ravi", "headwork": "Shahdara", "short_name": "Shahdara"},
    {"key": "Balloki", "api_name": "Balloki", "river": "Ravi", "headwork": "Balloki", "short_name": "Balloki"},
    {"key": "Sidhnai", "api_name": "Sidhnai", "river": "Ravi", "headwork": "Sidhnai", "short_name": "Sidhnai"},
    
    # Chenab River stations (4-6)
    {"key": "Marala", "api_name": "Marala", "river": "Chenab", "headwork": "Marala", "short_name": "Marala"},
    {"key": "Trimmu", "api_name": "Trimmu", "river": "Chenab", "headwork": "Trimmu", "short_name": "Trimmu"},
    {"key": "Panjnad", "api_name": "Panjnad", "river": "Chenab", "headwork": "Panjnad", "short_name": "Panjnad"},
    
    # Sutlej River stations (7-9)
    {"key": "Ganda Singh Wala", "api_name": "Ganda Singh Wala", "river": "Sutlej", "headwork": "Ganda Singh Wala", "short_name": "G. S. Wala"},
    {"key": "Sulemanki", "api_name": "Sulemanki", "river": "Sutlej", "headwork": "Sulemanki", "short_name": "Sulemanki"},
    {"key": "Islam", "api_name": "Islam", "river": "Sutlej", "headwork": "Islam", "short_name": "Islam"},
    
    # Indus River station (10) - standalone
    {"key": "Guddu", "api_name": "Guddu", "river": "Indus", "headwork": "Guddu", "short_name": "Guddu"},
]

# River groupings for connector lines
GROUPS = [
    [0, 1, 2, 3],  # Ravi River: Jassar(0) -> Shahdara(1) -> Balloki(2) -> Sidhnai(3)
    [4, 5, 6],     # Chenab River: Marala(4) -> Trimmu(5) -> Panjnad(6)
    [7, 8, 9],     # Sutlej River: G. S. Wala(7) -> Sulemanki(8) -> Islam(9)
    # Indus River: Guddu(10) - standalone, no connections
]

def fetch_api_data():
    """Fetch data from the API"""
    try:
        data = {'API_KEY': API_KEY}
        response = requests.post(API_URL, data=data, timeout=1000)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching API data: {e}")
        sys.exit(1)

def get_last_timestamp():
    """Get the last processed timestamp"""
    try:
        with open(TIMESTAMP_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_timestamp(timestamp):
    """Save the current timestamp"""
    with open(TIMESTAMP_FILE, 'w') as f:
        f.write(timestamp)

def should_generate_dashboard(api_data):
    """Determine if we should generate a new dashboard based ONLY on timestamp change"""
    current_timestamp = api_data.get('latest_reading_time', '')
    last_timestamp = get_last_timestamp()
    
    print(f"🕐 Current API timestamp: {current_timestamp}")
    print(f"🕐 Last saved timestamp: {last_timestamp}")
    
    if current_timestamp != last_timestamp:
        print("✅ TIMESTAMP CHANGED - Generating new dashboard")
        return True, current_timestamp
    else:
        print("❌ TIMESTAMP UNCHANGED - Skipping dashboard generation")
        return False, current_timestamp

def parse_datetime(datetime_str):
    """Parse API datetime and convert to 12-hour format"""
    try:
        dt_part = datetime_str.replace(" PST", "").replace(" PKT", "")
        dt = datetime.strptime(dt_part, "%d-%b-%Y %H:%M")
        date_text = dt.strftime("%d %b %Y")
        time_text = dt.strftime("%I:%M %p").lstrip('0')
        return date_text, time_text
    except Exception as e:
        print(f"Error parsing datetime: {e}")
        now = datetime.now()
        return now.strftime("%d %b %Y"), now.strftime("%I:%M %p").lstrip('0')

def find_station_data(api_data, station_name):
    """Find station data in API response"""
    for station in api_data.get('data', []):
        if station.get('name') == station_name:
            return station
    return None

def format_flow(discharge):
    """Format discharge value with commas"""
    try:
        clean_discharge = str(discharge).replace(',', '')
        formatted = f"{int(clean_discharge):,} cusecs"
        return formatted
    except (ValueError, TypeError):
        return f"{discharge} cusecs"

def calculate_required_height(num_stations):
    """Calculate the minimum height needed for all stations"""
    # Constants for layout calculation
    HEADER_H = 250
    SEP_H = 13
    MARGIN_TOP = 26
    BOTTOM_BAR_H = 32
    
    # Per-station spacing
    ROW_GAP = 20
    GROUP_GAP = 24
    TITLE_GAP = 12
    
    # Font sizes (approximate heights)
    FONT_H1_SIZE = 48
    FONT_BODY_SIZE = 34
    LINE_HEIGHT_MULTIPLIER = 1.35
    
    # Calculate content height
    content_start = HEADER_H + SEP_H + MARGIN_TOP
    
    # Each station needs:
    # - Title line (FONT_H1_SIZE)
    # - Title gap (TITLE_GAP)
    # - Status lines (2 lines max, each FONT_BODY_SIZE * LINE_HEIGHT_MULTIPLIER)
    # - Row gap (ROW_GAP)
    status_height = int(FONT_BODY_SIZE * LINE_HEIGHT_MULTIPLIER * 2)  # Max 2 lines
    per_station_height = FONT_H1_SIZE + TITLE_GAP + status_height + ROW_GAP
    
    # Add group gaps after Ravi (after station 3), Chenab (after station 6), Sutlej (after station 9)
    # That's 3 group gaps total
    num_group_gaps = 3
    total_content_height = (num_stations * per_station_height) + (num_group_gaps * GROUP_GAP)
    
    # Add some padding for safety
    safety_padding = 100
    required_height = content_start + total_content_height + BOTTOM_BAR_H + safety_padding
    
    # Minimum height should be at least the original 1920
    min_height = 1920
    final_height = max(min_height, required_height)
    
    print(f"📏 Height calculation:")
    print(f"   Stations: {num_stations}")
    print(f"   Per station height: {per_station_height}")
    print(f"   Group gaps: {num_group_gaps}")
    print(f"   Calculated height: {required_height}")
    print(f"   Final height: {final_height}")
    
    return final_height

def create_dashboard(api_data):
    """Create the dashboard with API data using correct station order"""
    latest_time = api_data.get('latest_reading_time', '')
    date_text, time_text = parse_datetime(latest_time)
    
    # Debug: Print all available station names in API data
    print("=== DEBUG: Available stations in API data ===")
    api_stations = api_data.get('data', [])
    for station in api_stations:
        print(f"  - {station.get('name', 'UNNAMED')}")
    print("=" * 50)
    
    # --- Filename construction with robust 12-hour time handling ---
    try:
        dt_part = latest_time.replace(" PST", "").replace(" PKT", "")
        dt = datetime.strptime(dt_part, "%d-%b-%Y %H:%M")
        day = str(dt.day)  # No leading zero
        month = dt.strftime("%b")
        
        # Derive hour in 12-hour clock manually
        hour24 = dt.hour
        if hour24 == 0:
            hour12 = 12
            ampm = "AM"
        elif 1 <= hour24 < 12:
            hour12 = hour24
            ampm = "AM"
        elif hour24 == 12:
            hour12 = 12
            ampm = "PM"
        else:  # 13-23
            hour12 = hour24 - 12
            ampm = "PM"
        
        # If minutes are not zero, include them; else omit minutes
        if dt.minute == 0:
            time_part = f"{hour12} {ampm}"  # e.g., 1 PM
        else:
            time_part = f"{hour12}-{dt.minute:02d} {ampm}"  # e.g., 1-30 PM
        
        outfile = f"{day} {month} {time_part}.png"
        
    except Exception as e:
        print(f"Error creating filename from API datetime '{latest_time}': {e}")
        now = datetime.now()
        day = str(now.day)
        month = now.strftime("%b")
        hour24 = now.hour
        
        if hour24 == 0:
            hour12 = 12; ampm = "AM"
        elif 1 <= hour24 < 12:
            hour12 = hour24; ampm = "AM"
        elif hour24 == 12:
            hour12 = 12; ampm = "PM"
        else:
            hour12 = hour24 - 12; ampm = "PM"
        
        if now.minute == 0:
            time_part = f"{hour12} {ampm}"
        else:
            time_part = f"{hour12}-{now.minute:02d} {ampm}"
        
        outfile = f"{day} {month} {time_part}.png"
    
    # Process stations in the correct order with {rivername} at {headwork} format
    rows = []
    for station_info in STATION_ORDER:
        api_station = find_station_data(api_data, station_info['api_name'])
        
        # Create title in {rivername} at {headwork} format
        title = f"{station_info['river']} at {station_info['headwork']}"
        
        if api_station:
            status = api_station.get('status', 'NORMAL')
            severity = SEVERITY_DISPLAY.get(status, 'Normal')
            flow = api_station.get('outflow_discharge', api_station.get('inflow_discharge', '0'))
            flow_formatted = format_flow(flow)
            trend = api_station.get('outflow_trend', api_station.get('inflow_trend', 'Steady'))
            
            print(f"✅ Found station: {station_info['api_name']}")
            rows.append({
                "title": title,
                "severity": severity,
                "flow": flow_formatted,
                "trend": trend,
                "short_name": station_info['short_name'],
                "status": status
            })
        else:
            print(f"❌ Station {station_info['api_name']} not found in API data - using default values")
            rows.append({
                "title": title,
                "severity": "Normal",
                "flow": "0 cusecs",
                "trend": "Steady",
                "short_name": station_info['short_name'],
                "status": "NORMAL"
            })
    
    print(f"📊 Total stations to display: {len(rows)}")
    for i, row in enumerate(rows):
        print(f"  {i}: {row['short_name']} - {row['severity']} - {row['title']}")
    
    # Debug: Print the corrected groupings
    print("\n=== CORRECTED RIVER GROUPINGS ===")
    river_names = ["Ravi River", "Chenab River", "Sutlej River"]
    for i, group in enumerate(GROUPS):
        river_name = river_names[i] if i < len(river_names) else f"Group {i+1}"
        stations_in_group = [rows[j]['short_name'] for j in group if j < len(rows)]
        print(f"{river_name}: {' -> '.join(stations_in_group)}")
    print(f"Indus River: {rows[10]['short_name']} (standalone)")
    print("=" * 50)
    
    return rows, date_text, time_text, outfile

# === Font Setup ===
def pick_font(paths, size):
    """Pick the first available font from paths"""
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

# Font paths for different operating systems
WIN = "C:/Windows/Fonts"
LIN = "/usr/share/fonts/truetype/dejavu"
MAC = "/System/Library/Fonts"

# Font definitions
FONT_TITLE = pick_font([f"{WIN}/segoeuib.ttf", f"{LIN}/DejaVuSans-Bold.ttf", f"{MAC}/Arial Bold.ttf"], 62)
FONT_DATE = pick_font([f"{WIN}/segoeuib.ttf", f"{LIN}/DejaVuSans-Bold.ttf", f"{MAC}/Arial Bold.ttf"], 38)
FONT_H1 = pick_font([f"{WIN}/segoeuib.ttf", f"{LIN}/DejaVuSans-Bold.ttf", f"{MAC}/Arial Bold.ttf"], 48)
FONT_BODY = pick_font([f"{WIN}/segoeui.ttf", f"{LIN}/DejaVuSans.ttf", f"{MAC}/Arial.ttf"], 34)
FONT_BODY_B = pick_font([f"{WIN}/segoeuib.ttf", f"{LIN}/DejaVuSans-Bold.ttf", f"{MAC}/Arial Bold.ttf"], 34)
FONT_RIGHT = pick_font([f"{WIN}/segoeuib.ttf", f"{LIN}/DejaVuSans-Bold.ttf", f"{MAC}/Arial Bold.ttf"], 28)

# === Layout Constants ===
MARGIN_L = 48
TEXT_W = 690
TITLE_GAP = 12
ROW_GAP = 20
GROUP_GAP = 24
HEADER_H = 250
SEP_H = 13
TIMEX = W - 230
DOT_R = 24
LINE_W = 6
LABEL_PADX = 44

def tlen(draw, txt, font):
    """Get text length"""
    return draw.textlength(txt, font=font)

def draw_status(draw, x, y, maxw, sev, flow, trend):
    """Draw status with proper formatting and wrapping"""
    full = f"Status – {sev} Flood ({flow}) and {trend} Trend"
    lh = int(FONT_BODY.size * 1.35)
    
    if tlen(draw, full, FONT_BODY) <= maxw:
        # Single line layout
        cx = x
        def put(s, f, col):
            nonlocal cx
            draw.text((cx, y), s, font=f, fill=col)
            cx += tlen(draw, s, f)
        
        put("Status – ", FONT_BODY_B, "#111111")
        put(f"{sev} Flood", FONT_BODY_B, SEVERITY_COLORS.get(sev.upper().replace(" ", "_"), "#0F8A26"))
        put(" (", FONT_BODY, "#111111")
        put(flow, FONT_BODY_B, "#111111")
        put(") and ", FONT_BODY, "#111111")
        put(trend, FONT_BODY_B, TREND_COLORS.get(trend, "#008000"))
        put(" Trend", FONT_BODY, "#111111")
        
        return y + lh
    
    # Two-line layout
    cx = x
    draw.text((cx, y), "Status – ", font=FONT_BODY_B, fill="#111111")
    cx += tlen(draw, "Status – ", FONT_BODY_B)
    draw.text((cx, y), f"{sev} Flood", font=FONT_BODY_B, fill=SEVERITY_COLORS.get(sev.upper().replace(" ", "_"), "#0F8A26"))
    cx += tlen(draw, f"{sev} Flood", FONT_BODY_B)
    draw.text((cx, y), " (", font=FONT_BODY, fill="#111111")
    cx += tlen(draw, " (", FONT_BODY)
    draw.text((cx, y), flow, font=FONT_BODY_B, fill="#111111")
    cx += tlen(draw, flow, FONT_BODY_B)
    draw.text((cx, y), ")", font=FONT_BODY, fill="#111111")
    
    y2 = y + lh
    cx2 = x
    draw.text((cx2, y2), "and ", font=FONT_BODY, fill="#111111")
    cx2 += tlen(draw, "and ", FONT_BODY)
    draw.text((cx2, y2), trend, font=FONT_BODY_B, fill=TREND_COLORS.get(trend, "#008000"))
    cx2 += tlen(draw, trend, FONT_BODY_B)
    draw.text((cx2, y2), " Trend", font=FONT_BODY, fill="#111111")
    
    return y2 + lh

def generate_image(rows, date_text, time_text, outfile):
    """Generate the dashboard image with dynamic height"""
    # Calculate required height based on number of stations
    H = calculate_required_height(len(rows))
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    
    # Header band
    d.rectangle([0, 0, W, HEADER_H], fill=HEADER_GREEN)
    
    # Logo positioning
    LOGO_W, LOGO_H = 170, 170
    LOGO_GAP = 30
    logo_x = MARGIN_L
    logo_y = (HEADER_H - LOGO_H) // 2
    
    try:
        logo = Image.open("ndma_logo.png").convert("RGBA").resize((LOGO_W, LOGO_H))
        img.paste(logo, (logo_x, logo_y), logo)
        has_logo = True
    except Exception:
        has_logo = False
        print("Warning: Logo file not found")
    
    # Calculate available space for text block
    if has_logo:
        text_start_x = logo_x + LOGO_W + LOGO_GAP
        available_width = W - text_start_x - MARGIN_L
    else:
        text_start_x = MARGIN_L
        available_width = W - 2 * MARGIN_L
    
    # Header text content
    title1 = "NEOC Daily Rivers"
    title2 = "Situation Update"
    LEAD_AFTER_LINE1 = 10
    LEAD_AFTER_LINE2 = 20
    
    line1_width = d.textlength(title1, font=FONT_TITLE)
    line2_width = d.textlength(title2, font=FONT_TITLE)
    
    date_time_gap = 60
    date_time_width = d.textlength(date_text, font=FONT_DATE) + date_time_gap + d.textlength(time_text, font=FONT_DATE)
    
    block_width = max(line1_width, line2_width, date_time_width)
    text_block_x = text_start_x + (available_width - block_width) // 2
    
    block_height = FONT_TITLE.size + LEAD_AFTER_LINE1 + FONT_TITLE.size + LEAD_AFTER_LINE2 + FONT_DATE.size
    text_block_y = (HEADER_H - block_height) // 2
    
    y_text = text_block_y
    
    # Draw header text
    line1_x = text_block_x + (block_width - line1_width) // 2
    d.text((line1_x, y_text), title1, font=FONT_TITLE, fill="white")
    y_text += FONT_TITLE.size + LEAD_AFTER_LINE1
    
    line2_x = text_block_x + (block_width - line2_width) // 2
    d.text((line2_x, y_text), title2, font=FONT_TITLE, fill="white")
    y_text += FONT_TITLE.size + LEAD_AFTER_LINE2
    
    date_time_start_x = text_block_x + (block_width - date_time_width) // 2
    d.text((date_time_start_x, y_text), date_text, font=FONT_DATE, fill="white")
    time_x = date_time_start_x + d.textlength(date_text, font=FONT_DATE) + date_time_gap
    d.text((time_x, y_text), time_text, font=FONT_DATE, fill="white")
    
    # White separator
    d.rectangle([0, HEADER_H, W, HEADER_H + SEP_H], fill="white")
    
    # Body content
    y = HEADER_H + SEP_H + 26
    dot_ys = []
    
    for i, r in enumerate(rows):
        d.text((MARGIN_L, y), f"{r['title']}:", font=FONT_H1, fill="#111111")
        y += FONT_H1.size + TITLE_GAP
        
        bottom = draw_status(d, MARGIN_L, y, TEXT_W, r["severity"], r["flow"], r["trend"])
        mid = (y + bottom) // 2
        dot_ys.append(mid)
        y = bottom + ROW_GAP
        
        # Add group gaps after each river section
        # After Ravi (station 3), Chenab (station 6), Sutlej (station 9)
        if i in (3, 6, 9):  # After Sidhnai, Panjnad, Islam
            y += GROUP_GAP
    
    # Right-side dots + labels
    for i, r in enumerate(rows):
        ydot = dot_ys[i]
        color = SEVERITY_COLORS.get(r["status"], "#0F8A26")
        d.ellipse([TIMEX - DOT_R, ydot - DOT_R, TIMEX + DOT_R, ydot + DOT_R], fill=color, outline=None)
        d.text((TIMEX + LABEL_PADX, ydot - FONT_RIGHT.size // 2), r["short_name"], font=FONT_RIGHT, fill="#1a1a1a")
        print(f"Station {i} ({r['short_name']}): Y position = {ydot}")
    
    print(f"Image height: {H}, Last station Y: {max(dot_ys) if dot_ys else 0}")
    
    # Draw connectors with correct river groupings
    print("\n=== DRAWING CONNECTORS ===")
    river_names = ["Ravi", "Chenab", "Sutlej"]
    for group_idx, group in enumerate(GROUPS):
        river_name = river_names[group_idx] if group_idx < len(river_names) else f"Group {group_idx+1}"
        print(f"Drawing connectors for {river_name} River: {group}")
        
        for a, b in zip(group, group[1:]):
            if a < len(dot_ys) and b < len(dot_ys):  # Safety check
                y1, y2 = dot_ys[a], dot_ys[b]
                d.line([TIMEX, y1 + DOT_R, TIMEX, y2 - DOT_R], fill="#222222", width=LINE_W)
                print(f"  Connected {rows[a]['short_name']} (pos {a}) to {rows[b]['short_name']} (pos {b})")
    
    # Indus River (Guddu) is standalone - no connections
    print(f"Indus River: {rows[10]['short_name']} (standalone - no connections)")
    
    # Bottom bar
    d.rectangle([0, H - 32, W, H], fill=HEADER_GREEN)
    
    img.save(outfile, "PNG")
    return outfile

def main():
    """Main function with timestamp-only adaptive generation"""
    print("=== RIVER DASHBOARD GENERATOR ===")
    print("Fetching API data...")
    
    api_data = fetch_api_data()
    
    print("Checking for timestamp changes...")
    should_generate, current_timestamp = should_generate_dashboard(api_data)
    
    if should_generate:
        print("📈 Generating new dashboard...")
        rows, date_text, time_text, outfile = create_dashboard(api_data)
        generated_file = generate_image(rows, date_text, time_text, outfile)
        
        # Save the new timestamp
        save_timestamp(current_timestamp)
        
        print(f"✅ Generated: {generated_file}")
        print(f"📝 Saved timestamp: {current_timestamp}")
    else:
        print("⏭️ No update needed - timestamp unchanged")
        print("💡 Dashboard generation skipped to save resources")

if __name__ == "__main__":
    main()
