# Climbing Route Scraper

A web scraper that extracts climbing area and route data from Mountain Project and stores it in a MySQL database. This tool crawls Mountain Project URLs to collect comprehensive climbing information including areas, routes, ratings, and location hierarchies.

## Features

- **Automated Web Scraping**: Uses Selenium WebDriver with headless Chrome/Chromium
- **Hierarchical Data Collection**: Crawls parent/child relationships between climbing areas
- **MySQL Database Integration**: Stores data in a structured relational database
- **Docker Support**: Containerized deployment for easy setup and portability
- **Environment Configuration**: Secure credential management via `.env` files

## Database Schema

The scraper populates a MySQL database with the following data structures:

### Climbing Areas

- **Name**: Area name
- **ID**: Mountain Project unique identifier
- **Latitude/Longitude**: Geographic coordinates
- **Parent ID**: Reference to parent area (for hierarchy)

### Routes

- **Name**: Route name
- **ID**: Mountain Project unique identifier  
- **Latitude/Longitude**: Geographic coordinates
- **Parent ID**: Reference to parent area
- **Rating**: Climbing grade (e.g., 5.11c, V6)

### Data Hierarchy

The scraper maintains the Mountain Project location hierarchy:

```txt
All Locations (root)
├── State (Sub-Area Level 1)
│   ├── Region (Sub-Area Level 2)
│   │   ├── Crag (Sub-Area Level 3)
│   │   │   └── Routes
│   │   └── More Areas...
│   └── More Regions...
└── More States...
```

## Requirements

- Python 3.11+
- Chrome/Chromium browser (for Docker)
- MySQL database
- Required Python packages (see `requirements.txt`)

## Installation & Setup

### Option 1: Docker (Recommended)

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd route_scraper
   ```

2. **Configure environment variables**:

   Create a `.env` file with your database credentials:

   ```env
   DB_HOST=your-database-host
   DB_USER=your-username
   DB_PASSWORD=your-password
   DB_NAME=your-database-name
   DB_PORT=3306
   ```

3. **Build the Docker image**:

   ```bash
   docker build -t route-scraper .
   ```

4. **Run the scraper**:

   ```bash
   docker run --env-file .env route-scraper "https://www.mountainproject.com/area/105792216/nevermind-wall"
   ```

### Option 2: Local Installation

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Install Chrome/Chromium and ChromeDriver**

3. **Configure environment variables** (create `.env` file as above)

4. **Run the scraper**:

   ```bash
   python scrape_routes.py "https://www.mountainproject.com/area/105792216/nevermind-wall"
   ```

## Usage

### Basic Usage

```bash
python scrape_routes.py <MOUNTAIN_PROJECT_URL>
```

### Examples

```bash
# Scrape a specific climbing area
python scrape_routes.py "https://www.mountainproject.com/area/105792216/nevermind-wall"

# Scrape a state-level area (will crawl all sub-areas)
python scrape_routes.py "https://www.mountainproject.com/area/105708956/new-hampshire"

# Using Docker
docker run --env-file .env route-scraper "https://www.mountainproject.com/area/113064302/rock-lady"
```

### Data Collection Scope

When you provide a URL, the scraper will collect:

- The specific area or route from the URL
- All parent areas in the hierarchy (up to "All Locations")
- All child areas and routes (if an area URL is provided)
- Geographic coordinates and metadata

## Files

- **`scrape_routes.py`**: Main scraper script with Selenium WebDriver
- **`route_db_connect.py`**: Database connection and data insertion utilities
- **`create_schema.py`**: Database schema creation script
- **`requirements.txt`**: Python package dependencies
- **`Dockerfile`**: Container configuration for deployment
- **`.env`**: Environment variables (not tracked in git)

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | MySQL database hostname | `localhost` |
| `DB_USER` | Database username | `climber` |
| `DB_PASSWORD` | Database password | `secret123` |
| `DB_NAME` | Database name | `routes_db` |
| `DB_PORT` | Database port | `3306` |

## Important Notes

- Route and area IDs correspond to Mountain Project IDs for easy cross-referencing
- International climbing areas (outside the US) will have "International" as their Level 1 parent area
- The scraper respects Mountain Project's structure and maintains data integrity
- All coordinates are stored as latitude/longitude pairs

## Troubleshooting

### Common Docker Issues

If you encounter Chrome/Chromium errors in Docker, ensure your `get_driver()` function includes:

```python
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
```

### Database Connection Issues

- Verify your `.env` file contains correct database credentials
- Ensure your MySQL server is accessible from the Docker container
- Check that the database and required tables exist
