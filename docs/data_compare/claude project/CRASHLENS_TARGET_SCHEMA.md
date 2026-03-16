# CRASH LENS Target Schema — Frontend Expected Data Format

This document defines the exact column names, data types, and allowed values that the CRASH LENS frontend expects. ALL incoming crash data from ANY state must be normalized to match this schema exactly.

Source: Virginia VDOT CrashData_Basic (the original format before VDOT's 2026 schema change).

---

## Column 1: OBJECTID
- Type: Integer (auto-increment)
- Purpose: Unique row identifier
- Values: 1, 2, 3, ... (sequential integers)
- Notes: Generate if source doesn't have one

## Column 2: Document Nbr
- Type: String
- Purpose: Crash report document number
- Values: e.g., "170015012", "250064321"
- Notes: State-specific format, passthrough

## Column 3: Crash Year
- Type: Integer
- Purpose: Year the crash occurred
- Values: 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025
- Notes: Extract from crash date if not provided separately

## Column 4: Crash Date
- Type: DateTime string
- Purpose: Date of crash
- Format: `M/D/YYYY H:MM:SS AM` (e.g., "1/15/2024 5:00:00 AM")
- Notes: The "5:00:00 AM" suffix is an ArcGIS artifact (UTC offset). If source has date-only, append " 5:00:00 AM"

## Column 5: Crash Military Time
- Type: Integer (0-2359)
- Purpose: Time of crash in military format
- Values: 0, 1, 2, ..., 100, 101, ..., 2359
- Notes: No leading zeros. "0" = midnight, "1430" = 2:30 PM

## Column 6: Crash Severity
- Type: String (single character)
- Purpose: Most severe injury in the crash (KABCO scale)
- Allowed values:
  - `K` — Fatal
  - `A` — Incapacitating injury
  - `B` — Non-incapacitating injury
  - `C` — Possible injury
  - `O` — Property damage only

## Column 7: K_People
- Type: Integer
- Purpose: Number of people killed
- Values: 0, 1, 2, 3, 4

## Column 8: A_People
- Type: Integer
- Purpose: Number of people with incapacitating injuries
- Values: 0-54

## Column 9: B_People
- Type: Integer
- Purpose: Number of people with non-incapacitating injuries
- Values: 0-36

## Column 10: C_People
- Type: Integer
- Purpose: Number of people with possible injuries
- Values: 0-38

## Column 11: Persons Injured
- Type: Integer
- Purpose: Total persons injured (A+B+C)
- Values: 0-54

## Column 12: Pedestrians Killed
- Type: Integer
- Purpose: Number of pedestrians killed
- Values: 0-3

## Column 13: Pedestrians Injured
- Type: Integer
- Purpose: Number of pedestrians injured
- Values: 0-7

## Column 14: Vehicle Count
- Type: Integer
- Purpose: Number of vehicles involved
- Values: 1-75

## Column 15: Collision Type
- Type: String (numbered label)
- Allowed values:
  - `1. Rear End`
  - `2. Angle`
  - `3. Head On`
  - `4. Sideswipe - Same Direction`
  - `5. Sideswipe - Opposite Direction`
  - `6. Fixed Object in Road`
  - `7. Train`
  - `8. Non-Collision`
  - `9. Fixed Object - Off Road`
  - `10. Deer`
  - `11. Other Animal`
  - `12. Ped`
  - `13. Bicyclist`
  - `14. Motorcyclist`
  - `15. Backed Into`
  - `16. Other`
  - `Not Applicable`
  - `Not Provided`

## Column 16: Weather Condition
- Type: String (numbered label)
- Allowed values:
  - `1. No Adverse Condition (Clear/Cloudy)`
  - `3. Fog`
  - `4. Mist`
  - `5. Rain`
  - `6. Snow`
  - `7. Sleet/Hail`
  - `8. Smoke/Dust`
  - `9. Other`
  - `10. Blowing Sand, Soil, Dirt, or Snow`
  - `11. Severe Crosswinds`
  - `Not Applicable`

## Column 17: Light Condition
- Type: String (numbered label)
- Allowed values:
  - `1. Dawn`
  - `2. Daylight`
  - `3. Dusk`
  - `4. Darkness - Road Lighted`
  - `5. Darkness - Road Not Lighted`
  - `6. Darkness - Unknown Road Lighting`
  - `7. Unknown`
  - `Not Applicable`

## Column 18: Roadway Surface Condition
- Type: String (numbered label)
- Allowed values:
  - `1. Dry`
  - `2. Wet`
  - `3. Snowy`
  - `4. Icy`
  - `5. Muddy`
  - `6. Oil/Other Fluids`
  - `7. Other`
  - `8. Natural Debris`
  - `9. Water (Standing, Moving)`
  - `10. Slush`
  - `11. Sand, Dirt, Gravel`
  - `Not Applicable`
  - `Not Provided`

## Column 19: Relation To Roadway
- Type: String (numbered label)
- Allowed values:
  - `1. Main-Line Roadway`
  - `2. Acceleration/Deceleration Lanes`
  - `3. Gore Area (b/w Ramp and Highway Edgelines)`
  - `4. Collector/Distributor Road`
  - `5. On Entrance/Exit Ramp`
  - `6. Intersection at end of Ramp`
  - `7. Other location not listed above within an interchange area (median, shoulder , roadside)`
  - `8. Non-Intersection`
  - `9. Within Intersection`
  - `10. Intersection Related - Within 150 Feet`
  - `11. Intersection Related - Outside 150 Feet`
  - `12. Crossover Related`
  - `13. Driveway, Alley-Access - Related`
  - `14. Railway Grade Crossing`
  - `15. Other Crossing (Crossing for Bikes, School, etc.)`
  - `Not Applicable`
  - `Not Provided`

## Column 20: Roadway Alignment
- Type: String (numbered label)
- Allowed values:
  - `1. Straight - Level`
  - `2. Curve - Level`
  - `3. Grade - Straight`
  - `4. Grade - Curve`
  - `5. Hillcrest - Straight`
  - `6. Hillcrest - Curve`
  - `7. Dip - Straight`
  - `8. Dip - Curve`
  - `9. Other`
  - `10. On/Off Ramp`

## Column 21: Roadway Surface Type
- Type: String (numbered label)
- Allowed values:
  - `1. Concrete`
  - `2. Blacktop, Asphalt, Bituminous`
  - `3. Brick or Block`
  - `4. Slag, Gravel, Stone`
  - `5. Dirt`
  - `6. Other`
  - `Not Applicable`

## Column 22: Roadway Defect
- Type: String (numbered label)
- Allowed values:
  - `1. No Defects`
  - `2. Holes, Ruts, Bumps`
  - `3. Soft or Low Shoulder`
  - `4. Under Repair`
  - `5. Loose Material`
  - `6. Restricted Width`
  - `7. Slick Pavement`
  - `8. Roadway Obstructed`
  - `9. Other`
  - `10. Edge Pavement Drop Off`
  - `Not Applicable`
  - `Not Provided`

## Column 23: Roadway Description
- Type: String (numbered label)
- Allowed values:
  - `1. Two-Way, Not Divided`
  - `2. Two-Way, Divided, Unprotected Median`
  - `3. Two-Way, Divided, Positive Median Barrier`
  - `4. One-Way, Not Divided`
  - `5. Unknown`
  - `Not Applicable`
  - `Not Provided`

## Column 24: Intersection Type
- Type: String (numbered label)
- Allowed values:
  - `1. Not at Intersection`
  - `2. Two Approaches`
  - `3. Three Approaches`
  - `4. Four Approaches`
  - `5. Five-Point, or More`
  - `6. Roundabout`
  - `Not Applicable`
  - `Not Provided`

## Column 25: Traffic Control Type
- Type: String (numbered label)
- Allowed values:
  - `1. No Traffic Control`
  - `2. Officer or Flagger`
  - `3. Traffic Signal`
  - `4. Stop Sign`
  - `5. Slow or Warning Sign`
  - `6. Traffic Lanes Marked`
  - `7. No Passing Lines`
  - `8. Yield Sign`
  - `9. One Way Road or Street`
  - `10. Railroad Crossing With Markings and Signs`
  - `11. Railroad Crossing With Signals`
  - `12. Railroad Crossing With Gate and Signals`
  - `13. Other`
  - `14. Ped Crosswalk`
  - `15. Reduced Speed - School Zone`
  - `16. Reduced Speed - Work Zone`
  - `17. Highway Safety Corridor`
  - `Not Applicable`

## Column 26: Traffic Control Status
- Type: String (numbered label)
- Allowed values:
  - `1. Yes - Working`
  - `2. Yes - Working and Obscured`
  - `3. Yes - Not Working`
  - `4. Yes - Not Working and Obscured`
  - `5. Yes - Missing`
  - `6. No Traffic Control Device Present`
  - `Not Applicable`
  - `Not Provided`

## Column 27: Work Zone Related
- Type: String (numbered label)
- Allowed values:
  - `1. Yes`
  - `2. No`
  - `Not Applicable`
  - `Not Provided`

## Column 28: Work Zone Location
- Type: String (numbered label)
- Allowed values:
  - `1. Advance Warning Area`
  - `2. Transition Area`
  - `3. Activity Area`
  - `4. Termination Area`

## Column 29: Work Zone Type
- Type: String (numbered label)
- Allowed values:
  - `1. Lane Closure`
  - `2. Lane Shift/Crossover`
  - `3. Work on Shoulder or Median`
  - `4. Intermittent or Moving Work`
  - `5. Other`

## Column 30: School Zone
- Type: String (numbered label)
- Allowed values:
  - `1. Yes`
  - `2. Yes - With School Activity`
  - `3. No`
  - `Not Applicable`
  - `Not Provided`

## Column 31: First Harmful Event
- Type: String (numbered label)
- Allowed values:
  - `1. Bank Or Ledge`
  - `2. Trees`
  - `3. Utility Pole`
  - `4. Fence Or Post`
  - `5. Guard Rail`
  - `6. Parked Vehicle`
  - `7. Tunnel, Bridge, Underpass, Culvert, etc.`
  - `8. Sign, Traffic Signal`
  - `9. Impact Cushioning Device`
  - `10. Other`
  - `11. Jersey Wall`
  - `12. Building/Structure`
  - `13. Curb`
  - `14. Ditch`
  - `15. Other Fixed Object`
  - `16. Other Traffic Barrier`
  - `17. Traffic Sign Support`
  - `18. Mailbox`
  - `19. Ped`
  - `20. Motor Vehicle In Transport`
  - `21. Train`
  - `22. Bicycle`
  - `23. Animal`
  - `24. Work Zone Maintenance Equipment`
  - `25. Other Movable Object`
  - `26. Unknown Movable Object`
  - `27. Other`
  - `28. Ran Off Road`
  - `29. Jack Knife`
  - `30. Overturn (Rollover)`
  - `31. Downhill Runaway`
  - `32. Cargo Loss or Shift`
  - `33. Explosion or Fire`
  - `34. Separation of Units`
  - `35. Cross Median`
  - `36. Cross Centerline`
  - `37. Equipment Failure (Tire, etc)`
  - `38. Immersion`
  - `39. Fell/Jumped From Vehicle`
  - `40. Thrown or Falling Object`
  - `41. Non-Collision Unknown`
  - `42. Other Non-Collision`

## Column 32: First Harmful Event Loc
- Type: String (numbered label)
- Allowed values:
  - `1. On Roadway`
  - `2. Shoulder`
  - `3. Median`
  - `4. Roadside`
  - `5. Gore`
  - `6. Separator`
  - `7. In Parking Lane or Zone`
  - `8. Off Roadway, Location Unknown`
  - `9. Outside Right-of-Way`
  - `Not Applicable`
  - `Not Provided`

## Columns 33-45: Boolean Flag Columns
All use `Yes` / `No` encoding EXCEPT Unrestrained? which uses `Belted` / `Unbelted`.

| # | Column Name | Values |
|---|-------------|--------|
| 33 | Alcohol? | Yes, No |
| 34 | Animal Related? | Yes, No |
| 35 | Unrestrained? | Belted, Unbelted |
| 36 | Bike? | Yes, No |
| 37 | Distracted? | Yes, No |
| 38 | Drowsy? | Yes, No |
| 39 | Drug Related? | Yes, No |
| 40 | Guardrail Related? | Yes, No |
| 41 | Hitrun? | Yes, No |
| 42 | Lgtruck? | Yes, No |
| 43 | Motorcycle? | Yes, No |
| 44 | Pedestrian? | Yes, No |
| 45 | Speed? | Yes, No |

## Column 46: Max Speed Diff
- Type: Integer
- Purpose: Speed differential
- Values: 1-165

## Column 47: RoadDeparture Type
- Type: String (code)
- Allowed values:
  - `NOT_RD`
  - `RD_LEFT`
  - `RD_RIGHT`
  - `RD_UNKNOWN`

## Column 48: Intersection Analysis
- Type: String (label)
- Allowed values:
  - `Not Intersection`
  - `Urban Intersection`
  - `VDOT Intersection`

## Columns 49-52: Additional Boolean Flags
All use `Yes` / `No` encoding.

| # | Column Name | Values |
|---|-------------|--------|
| 49 | Senior? | Yes, No |
| 50 | Young? | Yes, No |
| 51 | Mainline? | Yes, No |
| 52 | Night? | Yes, No |

## Column 53: VDOT District
- Type: String (numbered label)
- Allowed values:
  - `1. Bristol`
  - `2. Salem`
  - `3. Lynchburg`
  - `4. Richmond`
  - `5. Hampton Roads`
  - `6. Fredericksburg`
  - `7. Culpeper`
  - `8. Staunton`
  - `9. Northern Virginia`

## Column 54: Juris Code
- Type: Integer
- Purpose: Jurisdiction numeric code
- Values: 0-324

## Column 55: Physical Juris Name
- Type: String (formatted as "NNN. Name")
- Purpose: Jurisdiction display name
- Format: Three-digit zero-padded code + ". " + county/city name
- Examples: `000. Arlington County`, `043. Henrico County`, `100. Alexandria City`
- Notes: 324 unique values covering all Virginia counties and independent cities

## Column 56: Functional Class
- Type: String (coded label)
- Allowed values:
  - `1-Interstate (A,1)`
  - `2-Principal Arterial - Other Freeways and Expressways (B)`
  - `3-Principal Arterial - Other (E,2)`
  - `4-Minor Arterial (H,3)`
  - `5-Major Collector (I,4)`
  - `6-Minor Collector (5)`
  - `7-Local (J,6)`

## Column 57: Facility Type
- Type: String (coded label)
- Allowed values:
  - `1-One-Way Undivided`
  - `2-One-Way Divided`
  - `3-Two-Way Undivided`
  - `4-Two-Way Divided`
  - `5-Reversible Exclusively (e.g. 395R)`

## Column 58: Area Type
- Type: String (label)
- Allowed values:
  - `Rural`
  - `Urban`

## Column 59: SYSTEM
- Type: String (label)
- Allowed values:
  - `NonVDOT primary`
  - `NonVDOT secondary`
  - `VDOT Interstate`
  - `VDOT Primary`
  - `VDOT Secondary`

## Column 60: VSP
- Type: Integer
- Purpose: Virginia State Police division
- Values: 1-7

## Column 61: Ownership
- Type: String (numbered label)
- Allowed values:
  - `1. State Hwy Agency`
  - `2. County Hwy Agency`
  - `3. City or Town Hwy Agency`
  - `4. Federal Roads`
  - `5. Toll Roads Maintained by Others`
  - `6. Private/Unknown Roads`

## Column 62: Planning District
- Type: String (name)
- Allowed values:
  - `Accomack-Northampton`
  - `Central Shenandoah`
  - `Commonwealth Regional`
  - `Crater`
  - `Crater, Hampton Roads`
  - `Cumberland Plateau`
  - `George Washington Regional`
  - `Hampton Roads`
  - `Lenowisco`
  - `Middle Peninsula`
  - `Middle Peninsula, Hampton Roads`
  - `Mount Rogers`
  - `New River Valley`
  - `Northern Neck`
  - `Northern Shenandoah Valley`
  - `Northern Virginia`
  - `Rappahannock - Rapidan`
  - `Region 2000`
  - `Richmond Regional`
  - `Richmond Regional, Crater`
  - `Roanoke Valley-Alleghany`
  - `Roanoke Valley-Alleghany, West Piedmont`
  - `Southside`
  - `Thomas Jefferson`
  - `West Piedmont`

## Column 63: MPO Name
- Type: String (abbreviation)
- Allowed values: BRIS, CVIL, DAN, FRED, HAMP, HAR, KING, LYN, NOVA, NRV, RICH, ROAN, SAW, TCAT, WINC
- Notes: May be null if crash location is outside an MPO

## Column 64: RTE Name
- Type: String
- Purpose: Route identifier
- Format: e.g., "R-VA   IS00064WB", "R-VA   SR0076NB"
- Notes: State-specific, passthrough

## Column 65: RNS MP
- Type: Float
- Purpose: Route milepost
- Values: -0.07 to ~300+

## Column 66: Node
- Type: Integer
- Purpose: Network node ID
- Notes: State-specific, passthrough

## Column 67: Node Offset (ft)
- Type: Float
- Purpose: Distance from node in feet

## Column 68-69: x, y
- Type: Float
- Purpose: Longitude (x) and Latitude (y) coordinates
- Format: Decimal degrees, WGS84 (EPSG:4326)
- Example x: -77.436512
- Example y: 37.540231
- Notes: These are the primary location fields the frontend uses for mapping
