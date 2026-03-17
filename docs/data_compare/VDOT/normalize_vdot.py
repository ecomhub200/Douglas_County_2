"""
CRASH LENS — VDOT Numeric-to-Labeled Normalization Script
=========================================================
Claude Code Prompt: Paste this entire file into Claude Code to normalize
a VDOT numeric-encoded dataset to the CRASH LENS Frontend Standard Schema.

INPUT:  CSV with 73 columns, numeric codes (VDOT updated dataset)
OUTPUT: CSV with 69 columns, labeled strings (CRASH LENS standard)

Usage:
  python normalize_vdot.py input.csv output.csv
  python normalize_vdot.py input.csv  # writes to input_normalized.csv
"""

import pandas as pd
import sys
import os
from pathlib import Path

# ============================================================
# CONFIGURATION — All mapping tables
# ============================================================

# Columns that are EXTRA (not in the 69-col standard but preserved as passthrough)
# The frontend ignores columns it doesn't recognize
EXTRA_COLUMNS = ["Local Case CD", "Route or Street Name", "LAT", "LON"]

# Column renames: source → target
COLUMN_RENAMES = {
    "UnBelted?": "Unrestrained?",
    "Hit & Run?": "Hitrun?",
    "Large Vehicle?": "Lgtruck?",
    "Senior Driver?": "Senior?",
    "Young Driver?": "Young?",
}

# Expected output column order (69 columns)
TARGET_COLUMN_ORDER = [
    "OBJECTID", "Document Nbr", "Crash Year", "Crash Date", "Crash Military Time",
    "Crash Severity", "K_People", "A_People", "B_People", "C_People",
    "Persons Injured", "Pedestrians Killed", "Pedestrians Injured", "Vehicle Count",
    "Collision Type", "Weather Condition", "Light Condition", "Roadway Surface Condition",
    "Relation To Roadway", "Roadway Alignment", "Roadway Surface Type", "Roadway Defect",
    "Roadway Description", "Intersection Type", "Traffic Control Type", "Traffic Control Status",
    "Work Zone Related", "Work Zone Location", "Work Zone Type", "School Zone",
    "First Harmful Event", "First Harmful Event Loc",
    "Alcohol?", "Animal Related?", "Unrestrained?", "Bike?", "Distracted?", "Drowsy?",
    "Drug Related?", "Guardrail Related?", "Hitrun?", "Lgtruck?", "Motorcycle?", "Pedestrian?",
    "Speed?", "Max Speed Diff", "RoadDeparture Type", "Intersection Analysis",
    "Senior?", "Young?", "Mainline?", "Night?",
    "VDOT District", "Juris Code", "Physical Juris Name", "Functional Class",
    "Facility Type", "Area Type", "SYSTEM", "VSP", "Ownership",
    "Planning District", "MPO Name", "RTE Name", "RNS MP", "Node", "Node Offset (ft)",
    "x", "y",
]

# ============================================================
# VALUE MAPPING TABLES
# ============================================================

COLLISION_TYPE = {
    "0": "Not Applicable", "1": "1. Rear End", "2": "2. Angle", "3": "3. Head On",
    "4": "4. Sideswipe - Same Direction", "5": "5. Sideswipe - Opposite Direction",
    "6": "6. Fixed Object in Road", "7": "7. Train", "8": "8. Non-Collision",
    "9": "9. Fixed Object - Off Road", "10": "10. Deer", "11": "11. Other Animal",
    "12": "12. Ped", "13": "13. Bicyclist", "14": "14. Motorcyclist",
    "15": "15. Backed Into", "16": "16. Other", "99": "Not Provided",
}

WEATHER_CONDITION = {
    "1": "1. No Adverse Condition (Clear/Cloudy)", "3": "3. Fog", "4": "4. Mist",
    "5": "5. Rain", "6": "6. Snow", "7": "7. Sleet/Hail", "8": "8. Smoke/Dust",
    "9": "9. Other", "10": "10. Blowing Sand, Soil, Dirt, or Snow",
    "11": "11. Severe Crosswinds", "99": "Not Applicable",
}

LIGHT_CONDITION = {
    "1": "1. Dawn", "2": "2. Daylight", "3": "3. Dusk",
    "4": "4. Darkness - Road Lighted", "5": "5. Darkness - Road Not Lighted",
    "6": "6. Darkness - Unknown Road Lighting", "7": "7. Unknown", "99": "Not Applicable",
}

ROADWAY_SURFACE_CONDITION = {
    "1": "1. Dry", "2": "2. Wet", "3": "3. Snowy", "4": "4. Icy", "5": "5. Muddy",
    "6": "6. Oil/Other Fluids", "7": "7. Other", "8": "8. Natural Debris",
    "9": "9. Water (Standing, Moving)", "10": "10. Slush",
    "11": "11. Sand, Dirt, Gravel", "99": "Not Applicable",
}

RELATION_TO_ROADWAY = {
    "0": "Not Applicable", "1": "1. Main-Line Roadway",
    "2": "2. Acceleration/Deceleration Lanes",
    "3": "3. Gore Area (b/w Ramp and Highway Edgelines)",
    "4": "4. Collector/Distributor Road", "5": "5. On Entrance/Exit Ramp",
    "6": "6. Intersection at end of Ramp",
    "7": "7. Other location not listed above within an interchange area (median, shoulder , roadside)",
    "8": "8. Non-Intersection", "9": "9. Within Intersection",
    "10": "10. Intersection Related - Within 150 Feet",
    "11": "11. Intersection Related - Outside 150 Feet",
    "12": "12. Crossover Related", "13": "13. Driveway, Alley-Access - Related",
    "14": "14. Railway Grade Crossing",
    "15": "15. Other Crossing (Crossing for Bikes, School, etc.)", "99": "Not Provided",
}

ROADWAY_ALIGNMENT = {
    "1": "1. Straight - Level", "2": "2. Curve - Level", "3": "3. Grade - Straight",
    "4": "4. Grade - Curve", "5": "5. Hillcrest - Straight", "6": "6. Hillcrest - Curve",
    "7": "7. Dip - Straight", "8": "8. Dip - Curve", "9": "9. Other",
    "10": "10. On/Off Ramp", "99": "Not Applicable",
}

ROADWAY_SURFACE_TYPE = {
    "1": "1. Concrete", "2": "2. Blacktop, Asphalt, Bituminous",
    "3": "3. Brick or Block", "4": "4. Slag, Gravel, Stone",
    "5": "5. Dirt", "6": "6. Other", "99": "Not Applicable",
}

ROADWAY_DEFECT = {
    "0": "Not Applicable", "1": "1. No Defects", "2": "2. Holes, Ruts, Bumps",
    "3": "3. Soft or Low Shoulder", "4": "4. Under Repair", "5": "5. Loose Material",
    "6": "6. Restricted Width", "7": "7. Slick Pavement", "8": "8. Roadway Obstructed",
    "9": "9. Other", "10": "10. Edge Pavement Drop Off", "99": "Not Provided",
}

ROADWAY_DESCRIPTION = {
    "0": "Not Applicable", "1": "1. Two-Way, Not Divided",
    "2": "2. Two-Way, Divided, Unprotected Median",
    "3": "3. Two-Way, Divided, Positive Median Barrier",
    "4": "4. One-Way, Not Divided", "5": "5. Unknown", "99": "Not Provided",
}

INTERSECTION_TYPE = {
    "1": "1. Not at Intersection", "2": "2. Two Approaches",
    "3": "3. Three Approaches", "4": "4. Four Approaches",
    "5": "5. Five-Point, or More", "6": "6. Roundabout", "99": "Not Applicable",
}

TRAFFIC_CONTROL_TYPE = {
    "1": "1. No Traffic Control", "2": "2. Officer or Flagger",
    "3": "3. Traffic Signal", "4": "4. Stop Sign", "5": "5. Slow or Warning Sign",
    "6": "6. Traffic Lanes Marked", "7": "7. No Passing Lines", "8": "8. Yield Sign",
    "9": "9. One Way Road or Street",
    "10": "10. Railroad Crossing With Markings and Signs",
    "11": "11. Railroad Crossing With Signals",
    "12": "12. Railroad Crossing With Gate and Signals", "13": "13. Other",
    "14": "14. Ped Crosswalk", "15": "15. Reduced Speed - School Zone",
    "16": "16. Reduced Speed - Work Zone", "17": "17. Highway Safety Corridor",
    "99": "Not Applicable",
}

TRAFFIC_CONTROL_STATUS = {
    "1": "1. Yes - Working", "2": "2. Yes - Working and Obscured",
    "3": "3. Yes - Not Working", "4": "4. Yes - Not Working and Obscured",
    "5": "5. Yes - Missing", "6": "6. No Traffic Control Device Present",
    "99": "Not Applicable",
}

WORK_ZONE_RELATED = {"0": "Not Applicable", "1": "1. Yes", "2": "2. No", "99": "Not Provided"}

WORK_ZONE_LOCATION = {
    "0": "", "1": "1. Advance Warning Area", "2": "2. Transition Area",
    "3": "3. Activity Area", "4": "4. Termination Area", "99": "",
}

WORK_ZONE_TYPE = {
    "0": "", "1": "1. Lane Closure", "2": "2. Lane Shift/Crossover",
    "3": "3. Work on Shoulder or Median", "4": "4. Intermittent or Moving Work",
    "5": "5. Other", "99": "",
}

SCHOOL_ZONE = {
    "0": "Not Applicable", "1": "1. Yes", "2": "2. Yes - With School Activity",
    "3": "3. No", "99": "Not Provided",
}

FIRST_HARMFUL_EVENT_LOC = {
    "1": "1. On Roadway", "2": "2. Shoulder", "3": "3. Median", "4": "4. Roadside",
    "5": "5. Gore", "6": "6. Separator", "7": "7. In Parking Lane or Zone",
    "8": "8. Off Roadway, Location Unknown", "9": "9. Outside Right-of-Way",
    "99": "Not Applicable",
}

VDOT_DISTRICT = {
    "1": "1. Bristol", "2": "2. Salem", "3": "3. Lynchburg", "4": "4. Richmond",
    "5": "5. Hampton Roads", "6": "6. Fredericksburg", "7": "7. Culpeper",
    "8": "8. Staunton", "9": "9. Northern Virginia",
}

FUNCTIONAL_CLASS = {
    "INT": "1-Interstate (A,1)",
    "OFE": "2-Principal Arterial - Other Freeways and Expressways (B)",
    "OPA": "3-Principal Arterial - Other (E,2)",
    "MIA": "4-Minor Arterial (H,3)",
    "MAC": "5-Major Collector (I,4)",
    "MIC": "6-Minor Collector (5)",
    "LOC": "7-Local (J,6)",
}

FACILITY_TYPE = {
    "OUD": "1-One-Way Undivided", "OWD": "2-One-Way Divided",
    "TUD": "3-Two-Way Undivided", "TWD": "4-Two-Way Divided",
    "REX": "5-Reversible Exclusively (e.g. 395R)",
}

AREA_TYPE = {"0": "Rural", "1": "Urban"}

SYSTEM_MAP = {
    "1": "VDOT Interstate", "2": "VDOT Primary", "3": "VDOT Secondary",
    "4": "NonVDOT primary", "5": "NonVDOT secondary",
}

OWNERSHIP = {
    "1": "1. State Hwy Agency", "2": "2. County Hwy Agency",
    "3": "3. City or Town Hwy Agency", "4": "4. Federal Roads",
    "5": "5. Toll Roads Maintained by Others", "6": "6. Private/Unknown Roads",
}

BOOL_YES_NO = {"0": "No", "1": "Yes"}
UNBELTED_MAP = {"0": "Belted", "1": "Unbelted"}

ROAD_DEPARTURE = {"0": "NOT_RD", "1": "RD_LEFT", "2": "RD_RIGHT", "3": "RD_UNKNOWN"}
INTERSECTION_ANALYSIS = {"0": "Not Intersection", "1": "Urban Intersection", "2": "VDOT Intersection"}

PLANNING_DISTRICT = {
    "1": "Lenowisco", "2": "Cumberland Plateau", "3": "Mount Rogers",
    "4": "New River Valley", "5": "Roanoke Valley-Alleghany",
    "5,12": "Roanoke Valley-Alleghany, West Piedmont",
    "6": "Central Shenandoah", "7": "Northern Shenandoah Valley",
    "8": "Northern Virginia", "9": "Rappahannock - Rapidan",
    "10": "Thomas Jefferson", "11": "Region 2000", "12": "West Piedmont",
    "13": "Southside", "14": "Commonwealth Regional", "15": "Richmond Regional",
    "15,19": "Richmond Regional, Crater", "16": "George Washington Regional",
    "17": "Northern Neck", "18": "Middle Peninsula",
    "18,23": "Middle Peninsula, Hampton Roads", "19": "Crater",
    "19,23": "Crater, Hampton Roads", "22": "Accomack-Northampton",
    "23": "Hampton Roads",
}

# Physical Juris Name: numeric code → "NNN. Name" format (324 entries)
PHYSICAL_JURIS_NAME = {
    "0":"000. Arlington County","1":"001. Accomack County","2":"002. Albemarle County",
    "3":"003. Alleghany County","4":"004. Amelia County","5":"005. Amherst County",
    "6":"006. Appomattox County","7":"007. Augusta County","8":"008. Bath County",
    "9":"009. Bedford County","10":"010. Bland County","11":"011. Botetourt County",
    "12":"012. Brunswick County","13":"013. Buchanan County","14":"014. Buckingham County",
    "15":"015. Campbell County","16":"016. Caroline County","17":"017. Carroll County",
    "18":"018. Charles City County","19":"019. Charlotte County","20":"020. Chesterfield County",
    "21":"021. Clarke County","22":"022. Craig County","23":"023. Culpeper County",
    "24":"024. Cumberland County","25":"025. Dickenson County","26":"026. Dinwiddie County",
    "28":"028. Essex County","29":"029. Fairfax County","30":"030. Fauquier County",
    "31":"031. Floyd County","32":"032. Fluvanna County","33":"033. Franklin County",
    "34":"034. Frederick County","35":"035. Giles County","36":"036. Gloucester County",
    "37":"037. Goochland County","38":"038. Grayson County","39":"039. Greene County",
    "40":"040. Greensville County","41":"041. Halifax County","42":"042. Hanover County",
    "43":"043. Henrico County","44":"044. Henry County","45":"045. Highland County",
    "46":"046. Isle of Wight County","47":"047. James City County","48":"048. King George County",
    "49":"049. King & Queen County","50":"050. King William County","51":"051. Lancaster County",
    "52":"052. Lee County","53":"053. Loudoun County","54":"054. Louisa County",
    "55":"055. Lunenburg County","56":"056. Madison County","57":"057. Mathews County",
    "58":"058. Mecklenburg County","59":"059. Middlesex County","60":"060. Montgomery County",
    "62":"062. Nelson County","63":"063. New Kent County","65":"065. Northampton County",
    "66":"066. Northumberland County","67":"067. Nottoway County","68":"068. Orange County",
    "69":"069. Page County","70":"070. Patrick County","71":"071. Pittsylvania County",
    "72":"072. Powhatan County","73":"073. Prince Edward County","74":"074. Prince George County",
    "76":"076. Prince William County","77":"077. Pulaski County","78":"078. Rappahannock County",
    "79":"079. Richmond County","80":"080. Roanoke County","81":"081. Rockbridge County",
    "82":"082. Rockingham County","83":"083. Russell County","84":"084. Scott County",
    "85":"085. Shenandoah County","86":"086. Smyth County","87":"087. Southampton County",
    "88":"088. Spotsylvania County","89":"089. Stafford County","90":"090. Surry County",
    "91":"091. Sussex County","92":"092. Tazewell County","93":"093. Warren County",
    "95":"095. Washington County","96":"096. Westmoreland County","97":"097. Wise County",
    "98":"098. Wythe County","99":"099. York County",
    "100":"100. City of Alexandria","101":"101. Town of Big Stone Gap",
    "102":"102. City of Bristol","103":"103. City of Buena Vista",
    "104":"104. City of Charlottesville","105":"105. Town of Clifton Forge",
    "106":"106. City of Colonial Heights","107":"107. City of Covington",
    "108":"108. City of Danville","109":"109. City of Emporia",
    "110":"110. City of Falls Church","111":"111. City of Fredericksburg",
    "112":"112. Town of Front Royal","113":"113. City of Galax",
    "114":"114. City of Hampton","115":"115. City of Harrisonburg",
    "116":"116. City of Hopewell","117":"117. City of Lexington",
    "118":"118. City of Lynchburg","119":"119. Town of Marion",
    "120":"120. City of Martinsville","121":"121. City of Newport News",
    "122":"122. City of Norfolk","123":"123. City of Petersburg",
    "124":"124. City of Portsmouth","125":"125. Town of Pulaski",
    "126":"126. City of Radford","127":"127. City of Richmond",
    "128":"128. City of Roanoke","129":"129. City of Salem",
    "130":"130. Town of South Boston","131":"131. City of Chesapeake",
    "132":"132. City of Staunton","133":"133. City of Suffolk",
    "134":"134. City of Virginia Beach","136":"136. City of Waynesboro",
    "137":"137. City of Williamsburg","138":"138. City of Winchester",
    "139":"139. Town of Wytheville","140":"140. Town of Abingdon",
    "141":"141. Town of Bedford","142":"142. Town of Blackstone",
    "143":"143. Town of Bluefield","144":"144. Town of Farmville",
    "145":"145. City of Franklin","146":"146. City of Norton",
    "147":"147. City of Poquoson","148":"148. Town of Richlands",
    "149":"149. Town of Vinton","150":"150. Town of Blacksburg",
    "151":"151. City of Fairfax","152":"152. City of Manassas Park",
    "153":"153. Town of Vienna","154":"154. Town of Christiansburg",
    "155":"155. City of Manassas","156":"156. Town of Warrenton",
    "157":"157. Town of Rocky Mount","158":"158. Town of Tazewell",
    "159":"159. Town of Luray","160":"160. Town of Accomac",
    "161":"161. Town of Alberta","162":"162. Town of Altavista",
    "163":"163. Town of Amherst","164":"164. Town of Appalachia",
    "165":"165. Town of Appomattox","166":"166. Town of Ashland",
    "167":"167. Town of Belle Haven","168":"168. Town of Berryville",
    "169":"169. Town of Bloxom","170":"170. Town of Boones Mill",
    "171":"171. Town of Bowling Green","172":"172. Town of Boyce",
    "173":"173. Town of Boydton","174":"174. Town of Boykins",
    "175":"175. Town of Branchville","176":"176. Town of Bridgewater",
    "177":"177. Town of Broadway","178":"178. Town of Brodnax",
    "179":"179. Town of Brookneal","180":"180. Town of Buchanan",
    "181":"181. Town of Burkeville","182":"182. Town of Cape Charles",
    "183":"183. Town of Capron","184":"184. Town of Cedar Bluff",
    "185":"185. Town of Charlotte C.H.","186":"186. Town of Chase City",
    "187":"187. Town of Chatham","188":"188. Town of Cheriton",
    "189":"189. Town of Chilhowie","190":"190. Town of Chincoteague",
    "191":"191. Town of Claremont","192":"192. Town of Clarksville",
    "193":"193. Town of Cleveland","194":"194. Town of Clifton",
    "195":"195. Town of Clinchport","196":"196. Town of Clintwood",
    "198":"198. Town of Coeburn","199":"199. Town of Colonial Beach",
    "200":"200. Town of Columbia","201":"201. Town of Courtland",
    "202":"202. Town of Craigsville","203":"203. Town of Crewe",
    "204":"204. Town of Culpeper","205":"205. Town of Damascus",
    "206":"206. Town of Dayton","207":"207. Town of Dendron",
    "208":"208. Town of Dillwyn","209":"209. Town of Drakes Branch",
    "210":"210. Town of Dublin","211":"211. Town of Duffield",
    "212":"212. Town of Dumfries","213":"213. Town of Dungannon",
    "214":"214. Town of Eastville","215":"215. Town of Edinburg",
    "216":"216. Town of Elkton","217":"217. Town of Exmore",
    "218":"218. Town of Fincastle","219":"219. Town of Floyd",
    "220":"220. Town of Fries","221":"221. Town of Gate City",
    "222":"222. Town of Glade Spring","223":"223. Town of Glasgow",
    "224":"224. Town of Glen Lyn","225":"225. Town of Gordonsville",
    "226":"226. Town of Goshen","227":"227. Town of Gretna",
    "228":"228. Town of Grottoes","229":"229. Town of Grundy",
    "230":"230. Town of Halifax","231":"231. Town of Hallwood",
    "232":"232. Town of Hamilton","233":"233. Town of Haymarket",
    "234":"234. Town of Haysi","235":"235. Town of Herndon",
    "236":"236. Town of Hillsboro","237":"237. Town of Hillsville",
    "239":"239. Town of Honaker","240":"240. Town of Independence",
    "241":"241. Town of Iron Gate","242":"242. Town of Irvington",
    "243":"243. Town of Ivor","244":"244. Town of Jarratt",
    "245":"245. Town of Jonesville","246":"246. Town of Keller",
    "247":"247. Town of Kenbridge","248":"248. Town of Keysville",
    "249":"249. Town of Kilmarnock","250":"250. Town of LaCrosse",
    "251":"251. Town of Lawrenceville","252":"252. Town of Lebanon",
    "253":"253. Town of Leesburg","254":"254. Town of Louisa",
    "255":"255. Town of Lovettsville","256":"256. Town of Madison",
    "257":"257. Town of McKenney","258":"258. Town of Melfa",
    "259":"259. Town of Middleburg","260":"260. Town of Middletown",
    "261":"261. Town of Mineral","262":"262. Town of Monterey",
    "263":"263. Town of Montross","264":"264. Town of Mount Crawford",
    "265":"265. Town of Mount Jackson","266":"266. Town of Narrows",
    "267":"267. Town of Nassawadox","268":"268. Town of New Castle",
    "269":"269. Town of New Market","270":"270. Town of Newsoms",
    "271":"271. Town of Nickelsville","272":"272. Town of Occoquan",
    "273":"273. Town of Onancock","274":"274. Town of Onley",
    "275":"275. Town of Orange","276":"276. Town of Painter",
    "277":"277. Town of Pamplin City","278":"278. Town of Parksley",
    "279":"279. Town of Pearisburg","280":"280. Town of Pembroke",
    "281":"281. Town of Pennington Gap","282":"282. Town of Phenix",
    "283":"283. Town of Pocahontas","284":"284. Town of Port Royal",
    "285":"285. Town of Pound","286":"286. Town of Purcellville",
    "287":"287. Town of Quantico","288":"288. Town of Remington",
    "289":"289. Town of Rich Creek","290":"290. Town of Ridgeway",
    "291":"291. Town of Round Hill","292":"292. Town of Rural Retreat",
    "293":"293. Town of St. Charles","294":"294. Town of Saint Paul",
    "295":"295. Town of Saltville","296":"296. Town of Saxis",
    "297":"297. Town of Scottsburg","298":"298. Town of Scottsville",
    "299":"299. Town of Shenandoah","300":"300. Town of Smithfield",
    "301":"301. Town of South Hill","302":"302. Town of Stanardsville",
    "303":"303. Town of Stanley","304":"304. Town of Stephens City",
    "305":"305. Town of Stony Creek","306":"306. Town of Strasburg",
    "307":"307. Town of Stuart","308":"308. Town of Surry",
    "309":"309. Town of Tangier","310":"310. Town of Tappahannock",
    "311":"311. Town of The Plains","312":"312. Town of Timberville",
    "313":"313. Town of Toms Brook","314":"314. Town of Troutdale",
    "315":"315. Town of Troutville","316":"316. Town of Urbanna",
    "317":"317. Town of Victoria","318":"318. Town of Virgilina",
    "319":"319. Town of Wachapreague","320":"320. Town of Wakefield",
    "321":"321. Town of Warsaw","322":"322. Town of Washington",
    "323":"323. Town of Waverly","324":"324. Town of Weber City",
    "325":"325. Town of West Point","327":"327. Town of White Stone",
    "328":"328. Town of Windsor","329":"329. Town of Wise",
    "330":"330. Town of Woodstock","331":"331. Town of Hurt",
    "339":"339. Town of Clinchco",
}

# All value mapping rules: column_name → {source_value: target_value}
VALUE_MAP_RULES = {
    "Collision Type": COLLISION_TYPE,
    "Weather Condition": WEATHER_CONDITION,
    "Light Condition": LIGHT_CONDITION,
    "Roadway Surface Condition": ROADWAY_SURFACE_CONDITION,
    "Relation To Roadway": RELATION_TO_ROADWAY,
    "Roadway Alignment": ROADWAY_ALIGNMENT,
    "Roadway Surface Type": ROADWAY_SURFACE_TYPE,
    "Roadway Defect": ROADWAY_DEFECT,
    "Roadway Description": ROADWAY_DESCRIPTION,
    "Intersection Type": INTERSECTION_TYPE,
    "Traffic Control Type": TRAFFIC_CONTROL_TYPE,
    "Traffic Control Status": TRAFFIC_CONTROL_STATUS,
    "Work Zone Related": WORK_ZONE_RELATED,
    "Work Zone Location": WORK_ZONE_LOCATION,
    "Work Zone Type": WORK_ZONE_TYPE,
    "School Zone": SCHOOL_ZONE,
    "First Harmful Event Loc": FIRST_HARMFUL_EVENT_LOC,
    "VDOT District": VDOT_DISTRICT,
    "Functional Class": FUNCTIONAL_CLASS,
    "Facility Type": FACILITY_TYPE,
    "Area Type": AREA_TYPE,
    "SYSTEM": SYSTEM_MAP,
    "Ownership": OWNERSHIP,
    "Planning District": PLANNING_DISTRICT,
    "Physical Juris Name": PHYSICAL_JURIS_NAME,
    "RoadDeparture Type": ROAD_DEPARTURE,
    "Intersection Analysis": INTERSECTION_ANALYSIS,
}

# Boolean columns: 0→No, 1→Yes
BOOLEAN_COLS_YES_NO = [
    "Alcohol?", "Bike?", "Distracted?", "Animal Related?", "Drowsy?",
    "Drug Related?", "Guardrail Related?", "Motorcycle?", "Pedestrian?",
    "Speed?", "Mainline?", "Night?",
]

# Renamed boolean columns with their maps
RENAMED_BOOL_COLS = {
    "Hit & Run?": ("Hitrun?", BOOL_YES_NO),
    "Large Vehicle?": ("Lgtruck?", BOOL_YES_NO),
    "Senior Driver?": ("Senior?", BOOL_YES_NO),
    "Young Driver?": ("Young?", BOOL_YES_NO),
}

# Special: UnBelted? → Unrestrained? with 0→Belted, 1→Unbelted
UNBELTED_RENAME = ("UnBelted?", "Unrestrained?", UNBELTED_MAP)


# ============================================================
# IDEMPOTENCY CHECK
# ============================================================

def is_already_normalized(df):
    """Check if data appears to already be in labeled format."""
    checks = []
    
    # Check Functional Class — if it contains "Interstate" it's already labeled
    if "Functional Class" in df.columns:
        sample = df["Functional Class"].dropna().head(100)
        if any("Interstate" in str(v) for v in sample):
            checks.append(True)
        elif any(v in ["INT", "OFE", "OPA", "MIA", "MAC", "MIC", "LOC"] for v in sample.astype(str)):
            checks.append(False)
    
    # Check Ownership — if it contains "Agency" it's already labeled
    if "Ownership" in df.columns:
        sample = df["Ownership"].dropna().head(100)
        if any("Agency" in str(v) for v in sample):
            checks.append(True)
        elif all(str(v) in ["1","2","3","4","5","6"] for v in sample.astype(str)):
            checks.append(False)
    
    # Check Physical Juris Name — if it contains "County" it's already labeled
    if "Physical Juris Name" in df.columns:
        sample = df["Physical Juris Name"].dropna().head(100)
        if any("County" in str(v) or "City" in str(v) or "Town" in str(v) for v in sample):
            checks.append(True)
        elif all(str(v).isdigit() for v in sample.astype(str)):
            checks.append(False)
    
    # Check column names — if "Unrestrained?" exists, already renamed
    if "Unrestrained?" in df.columns and "UnBelted?" not in df.columns:
        checks.append(True)
    elif "UnBelted?" in df.columns:
        checks.append(False)
    
    if not checks:
        return False
    
    # If majority of checks say "already normalized"
    return sum(checks) > len(checks) / 2


# ============================================================
# NORMALIZATION PIPELINE
# ============================================================

def normalize(input_path, output_path=None):
    """Main normalization function."""
    
    print(f"Reading: {input_path}")
    df = pd.read_csv(input_path, dtype=str, low_memory=False)
    print(f"  Rows: {len(df):,} | Columns: {len(df.columns)}")
    
    # --- Idempotency check ---
    if is_already_normalized(df):
        print("  ⚠️  Data appears ALREADY NORMALIZED. Skipping transformation.")
        print("  (To force re-normalization, pass --force flag)")
        if "--force" not in sys.argv:
            return
    
    unmapped_log = []  # Track unmapped values
    
    # --- Step 1: Note extra columns (preserved, not dropped) ---
    for col in EXTRA_COLUMNS:
        if col in df.columns:
            print(f"  Extra column preserved: {col}")
    
    # --- Step 2: Apply value maps to categorical columns ---
    for col, vmap in VALUE_MAP_RULES.items():
        if col in df.columns:
            original = df[col].astype(str)
            df[col] = original.map(vmap)
            # Log unmapped values
            unmapped = df[col].isna() & original.notna() & (original != 'nan')
            if unmapped.any():
                bad_vals = original[unmapped].unique()
                unmapped_log.append((col, list(bad_vals)))
                print(f"  ⚠️  {col}: {unmapped.sum()} rows with unmapped values: {bad_vals[:5]}")
                # Keep original value for unmapped
                df.loc[unmapped, col] = original[unmapped]
    
    # --- Step 3: Apply boolean 0→No, 1→Yes ---
    for col in BOOLEAN_COLS_YES_NO:
        if col in df.columns:
            df[col] = df[col].astype(str).map(BOOL_YES_NO)
    
    # --- Step 4: Handle renamed + mapped columns ---
    # UnBelted? → Unrestrained?
    src, tgt, vmap = UNBELTED_RENAME
    if src in df.columns:
        df[tgt] = df[src].astype(str).map(vmap)
        df.drop(columns=[src], inplace=True)
        print(f"  Renamed+Mapped: {src} → {tgt}")
    
    for src, (tgt, vmap) in RENAMED_BOOL_COLS.items():
        if src in df.columns:
            df[tgt] = df[src].astype(str).map(vmap)
            df.drop(columns=[src], inplace=True)
            print(f"  Renamed+Mapped: {src} → {tgt}")
    
    # --- Step 5: Reorder columns to match target schema ---
    final_cols = []
    extra_cols = []
    for col in TARGET_COLUMN_ORDER:
        if col in df.columns:
            final_cols.append(col)
        else:
            print(f"  ⚠️  Missing target column: {col}")
    
    # Preserve extra columns not in target schema
    for col in df.columns:
        if col not in TARGET_COLUMN_ORDER:
            extra_cols.append(col)
    
    df = df[final_cols + extra_cols]
    
    # --- Step 6: Validation ---
    print("\n  === VALIDATION ===")
    
    # Check mandatory columns
    mandatory_checks = {
        "Crash Severity": lambda s: s.isin(["K", "A", "B", "C", "O"]),
        "Physical Juris Name": lambda s: s.str.contains(r'^\d{3}\.', na=False),
        "Functional Class": lambda s: s.str.contains(r'^[1-7]-', na=False),
        "Ownership": lambda s: s.str.contains(r'^\d\. ', na=False),
    }
    
    for col, check_fn in mandatory_checks.items():
        if col in df.columns:
            valid = check_fn(df[col].fillna(""))
            pct = valid.mean() * 100
            status = "✅" if pct > 95 else "⚠️" if pct > 50 else "❌"
            print(f"  {status} {col}: {pct:.1f}% valid")
    
    for coord in ["x", "y"]:
        if coord in df.columns:
            non_null = df[coord].notna().mean() * 100
            print(f"  {'✅' if non_null > 90 else '⚠️'} {coord}: {non_null:.1f}% non-null")
    
    # --- Step 7: Write output ---
    if output_path is None:
        base = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{base}_normalized.csv")
    
    df.to_csv(output_path, index=False)
    print(f"\n  ✅ Output: {output_path}")
    print(f"  Rows: {len(df):,} | Columns: {len(df.columns)}")
    
    if unmapped_log:
        print("\n  === UNMAPPED VALUES LOG ===")
        for col, vals in unmapped_log:
            print(f"  {col}: {vals}")
    
    return df


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python normalize_vdot.py <input.csv> [output.csv]")
        print("  Flags: --force  Force re-normalization even if data appears already normalized")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    
    normalize(input_file, output_file)
