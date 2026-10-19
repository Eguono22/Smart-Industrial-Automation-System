"""Industry discovery and solution planning catalog; no implied customer endorsements."""

CAPABILITIES = [
    {"id": key, "name": name, "status": status, "description": description}
    for key, name, status, description in [
        ("monitoring", "Live asset monitoring", "Available", "Six simulated sensor channels, live trends and machine status."),
        ("prediction", "Predictive maintenance", "Available", "Anomaly detection, health trends and demo remaining-life estimates."),
        ("control", "PLC control and interlocks", "Available", "Simulated ladder logic and optional Modbus TCP output-coil bridge; site engineering required."),
        ("alarms", "Alarm management", "Available", "Prioritized machine alarms and operator acknowledgement."),
        ("integration", "ERP, MES and CMMS integration", "Planned", "Connect work orders, production records and enterprise asset systems."),
        ("fleet", "Multi-site asset management", "Planned", "Asset hierarchy, site comparisons and fleet health views."),
        ("workorders", "Maintenance work orders", "Available", "Asset-linked tasks, manual assignments, due dates, priorities, completion notes and change history."),
        ("quality", "Quality and traceability", "Planned", "Inspection records, batch genealogy and nonconformance workflows."),
        ("production", "Production and OEE", "Planned", "Track availability, performance, quality, downtime and throughput."),
        ("energy", "Energy and resource management", "Planned", "Meter electricity, water, fuel and resource intensity."),
        ("environment", "Environmental monitoring", "Planned", "Track emissions, leaks, waste and environmental excursions."),
        ("safety", "Safety and compliance workflows", "Planned", "Inspection checklists, permits and incident records; no certification implied."),
        ("coldchain", "Cold-chain monitoring", "Planned", "Temperature excursions, storage conditions and shipment history."),
        ("inventory", "Inventory and logistics", "Planned", "Material levels, stock movements, warehouse assets and replenishment."),
        ("security", "Enterprise access and audit", "Planned", "Expanded enterprise controls, SSO and organization-wide audit reporting. Local account roles, customer access and task history are available."),
        ("connectivity", "Industrial connectivity", "Planned", "OPC UA, MQTT, BACnet and historian connectors with edge buffering."),
        ("reporting", "Reports and notifications", "Planned", "Scheduled reports and configurable escalation rules. Assignment and overdue emails are available through the SMTP worker."),
    ]
]

_BASE = ["monitoring", "prediction", "alarms", "fleet", "workorders", "security", "reporting"]
_ROWS = [
    ("manufacturing", "Manufacturing and automotive", "Factories, OEMs, component suppliers", "CNC machines, robots, presses and assembly lines", "production quality integration control", "OEE, unplanned downtime, scrap rate"),
    ("food", "Food and beverage", "Processors, dairies, breweries, packaging plants", "Mixers, fillers, ovens and refrigeration", "quality coldchain inventory energy", "Batch yield, temperature excursions, waste"),
    ("pharma", "Pharmaceuticals and biotechnology", "Drug manufacturers, biotech plants, laboratories", "Reactors, cleanroom utilities and freezers", "quality coldchain safety integration", "Batch deviations, equipment availability"),
    ("energy", "Power and renewable energy", "Utilities, independent power producers, solar and wind operators", "Turbines, generators, inverters and transformers", "energy environment control safety", "Availability, energy output, fault frequency"),
    ("oilgas", "Oil, gas and petrochemicals", "Refineries, pipeline operators, terminal owners", "Compressors, pumps, tanks and valves", "environment safety control inventory", "Leak events, downtime, energy intensity"),
    ("water", "Water and wastewater", "Municipal utilities, treatment operators, industrial water users", "Pumps, blowers, filtration and dosing equipment", "environment energy control quality", "Pump availability, resource use, process excursions"),
    ("mining", "Mining and minerals", "Mine operators, quarries, mineral processors", "Crushers, conveyors, mills and dewatering pumps", "production safety energy environment", "Throughput, equipment uptime, energy per tonne"),
    ("agriculture", "Agriculture and aquaculture", "Farms, greenhouses, irrigation operators, fish farms", "Irrigation pumps, feeders and climate equipment", "environment energy coldchain inventory", "Water use, equipment uptime, storage loss"),
    ("logistics", "Warehousing and logistics", "Distribution centers, third-party logistics providers, parcel hubs", "Conveyors, sorters, lifts and loading equipment", "inventory production integration energy", "Throughput, conveyor downtime, order delays"),
    ("buildings", "Commercial buildings and facilities", "Property managers, offices, malls and facility service providers", "HVAC, chillers, elevators and backup generators", "energy connectivity environment safety", "Energy intensity, comfort excursions, asset uptime"),
    ("healthcare", "Healthcare facilities", "Hospitals, clinics and healthcare facility operators", "HVAC, medical storage and backup power infrastructure", "coldchain energy safety inventory", "Utility availability, storage excursions, maintenance backlog"),
    ("datacenters", "Data centers and telecom", "Colocation operators, cloud facilities, telecom infrastructure owners", "Cooling, UPS, generators and power distribution", "energy connectivity safety integration", "Cooling efficiency, power availability, thermal excursions"),
    ("transport", "Rail and public transport", "Rail operators, transit agencies, depot maintainers", "Depot machinery, escalators and station utilities", "safety energy inventory integration", "Asset availability, service interruptions, repair time"),
    ("marine", "Marine and ports", "Port authorities, terminal operators, ship maintenance providers", "Cranes, pumps, shore power and cargo equipment", "inventory energy safety environment", "Crane availability, turnaround time, resource use"),
    ("aviation", "Aviation and airports", "Airports, ground handlers, aerospace manufacturers", "Baggage systems, ground equipment and facility utilities", "quality safety inventory integration", "Baggage throughput, ground equipment downtime"),
    ("construction", "Construction and infrastructure", "Contractors, infrastructure owners, equipment rental firms", "Site pumps, generators and construction machinery", "safety energy inventory environment", "Equipment utilization, fuel consumption, downtime"),
    ("chemicals", "Chemicals and materials", "Chemical producers, coatings plants, specialty material processors", "Reactors, agitators, dryers and transfer pumps", "quality environment safety control", "Batch consistency, energy intensity, downtime"),
    ("metals", "Metals and steel", "Steelworks, foundries, metal fabricators", "Furnaces, rolling mills, presses and extraction systems", "production quality energy environment", "Yield, furnace efficiency, equipment uptime"),
    ("paper", "Pulp, paper and packaging", "Paper mills, printers, packaging converters", "Dryers, rollers, cutters and packaging lines", "production quality energy inventory", "Web breaks, throughput, energy per unit"),
    ("textiles", "Textiles and apparel", "Spinning mills, weaving plants, dye houses", "Looms, spindles, dryers and dyeing machines", "production quality energy environment", "Fabric defects, machine utilization, water use"),
    ("waste", "Waste and recycling", "Recyclers, municipal waste operators, material recovery facilities", "Shredders, balers, sorting lines and digesters", "environment production safety energy", "Recovery rate, throughput, equipment downtime"),
    ("hospitality", "Hospitality and retail", "Hotels, restaurant groups, supermarkets and cold stores", "Refrigeration, kitchens, HVAC and water systems", "coldchain energy inventory safety", "Spoilage, energy use, service interruptions"),
    ("education", "Education and research", "Universities, training centers, research campuses", "Teaching rigs, laboratory utilities and campus assets", "energy safety connectivity integration", "Asset availability, maintenance backlog, energy use"),
    ("public", "Government and public infrastructure", "Municipalities, public works departments, infrastructure agencies", "Public lighting, pumps and municipal facilities", "energy environment safety integration", "Service availability, response time, operating cost"),
]
INDUSTRIES = [
    {"id": key, "name": name, "customers": customers, "assets": assets,
     "capabilities": list(dict.fromkeys(_BASE + extras.split())), "kpis": kpis}
    for key, name, customers, assets, extras, kpis in _ROWS
]
