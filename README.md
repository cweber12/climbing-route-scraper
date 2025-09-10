# DESCRIPTION

This task runs a web crawler at the Mountain Project URL specified to find climbing area and route data. 
This data is used to populate a MySQL database with: 

- Climbing Area: 
  - Name
  - ID  
  - Lat / Lon
  - Parent ID

- Route: 
  - Name
  - ID
  - Lat / Lon
  - Parent ID
  - Rating (e.g. 5.11c, V6)
  

## INSTRUCTIONS

1. Find the route on Mountain Project's website
2. Copy the URL
    - To load all routes from that route's parent area, navigate to the 
      parent area's page and copy that URL
3. Paste the URL into the CLI prompt below
4. Paste the prompt into the CLI and run

This will populate a MySQL database with:

- The area or route provided in the URL
- All parent and grandparent areas in the location hierarchy leading to that route or area
- If an area was selected, all child and grandchild areas and routes within them

Areas are stored in a database table based on how many levels they are from the root (All Locations) 

All Locations (all states)
    |
    Sub-Area Lev 1 (state)
        |
        Sub-Area Lev 2
            .....
            |
            Sub-Area Lev N
                |
                Route (1-M)

Tables contain:

- Route or Area ID
- Route or Area Name
- Coordinates
- Parent Area ID
- Rating (for Routes)

________________________________________________________________________________________

## NOTES

- Any routes or areas outside the US will have "International" as their LV 1 parent area
- Route and area IDs correspond to IDs on Mountain Project, so they can be easily linked.

________________________________________________________________________________________

## SETTING UP AND RUNNING DOCKER CONTAINER

### BUILD

docker build -t route-scraper .

## RUN

### Instructions

- Enter the URL of the Mountain Project area to pull sub-areas and routes from.
- Paste the URL here before copy/pasting to the command line (easier) 
  docker run --env-file .env route-scraper "<https://www.mountainproject.com/area/112191853/cave-boulder>"