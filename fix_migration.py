
import re

file_path = '/Users/mohithavala/.gemini/antigravity/scratch/wezu-backend/alembic/versions/77f44e2f3bd0_sync_broken_state.py'

preserved_tables = {
    'audit_logs', 'batch_jobs', 'batteries', 'blacklists', 'ecommerce_products', 'faq', 
    'firmware_updates', 'geofence', 'maintenanceschedule', 'otps', 'products', 'promo_codes', 
    'security_events', 'translation', 'users', 'addresses', 'batteryhealthlog', 'dealer_profiles', 
    'device_fingerprints', 'devices', 'fraud_check_logs', 'iot_devices', 'job_executions', 
    'kyc_documents', 'maintenancerecord', 'notification', 'notificationpreference', 'orders', 
    'payment_transactions', 'product_images', 'product_variants', 'referrals', 'risk_scores', 
    'search_histories', 'support_tickets', 'swap_preferences', 'vehicles', 'video_kyc_sessions', 
    'wallets', 'warehouses', 'continents', 'battery_specs', 'battery_batches', 'admin_users',
    'roles', 'permissions', 'role_permissions' 
}
# verify roles/permissions are in list (yes added them now)

with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
comment_block_create = False
current_table = None

# Regex patterns
create_table_regex = re.compile(r"^\s*op\.create_table\('(\w+)',")
create_index_regex = re.compile(r"^\s*op\.create_index\(.*(?:'(\w+)'|table_name='(\w+)')")
drop_table_regex = re.compile(r"^\s*op\.drop_table\('(\w+)'\)")
drop_index_regex = re.compile(r"^\s*op\.drop_index\(.*table_name='(\w+)'\)")

for line in lines:
    stripped = line.strip()
    
    # Check if line is already commented (skip processing but keep it)
    if stripped.startswith('#'):
        new_lines.append(line)
        continue

    # UPGRADE: create_table
    match_create = create_table_regex.match(line)
    if match_create:
        table_name = match_create.group(1)
        if table_name in preserved_tables:
            comment_block_create = True
            current_table = table_name
            new_lines.append("# " + line)
            continue
    
    # UPGRADE: create_index
    match_create_index = create_index_regex.match(line)
    if match_create_index:
        # group 1 or 2 depending on match
        table_name = match_create_index.group(1) or match_create_index.group(2)
        # Note: sometimes create_index 2nd arg is table name
        # ex: op.create_index(op.f('...'), 'table_name', ...)
        # My regex is weak. Let's refine: op.create_index(..., 'TABLE', ...)
        if not table_name:
             parts = line.split("'")
             if len(parts) >= 4 and parts[3] in preserved_tables:
                 table_name = parts[3]

        if table_name and table_name in preserved_tables:
            new_lines.append("# " + line)
            continue

    if comment_block_create:
        new_lines.append("# " + line)
        if stripped.endswith(')'):
            comment_block_create = False
            current_table = None
        continue

    # DOWNGRADE: drop_table
    match_drop = drop_table_regex.match(line)
    if match_drop:
        table_name = match_drop.group(1)
        if table_name in preserved_tables:
            new_lines.append("# " + line)
            continue

    # DOWNGRADE: drop_index
    match_drop_index = drop_index_regex.match(line)
    if match_drop_index:
        table_name = match_drop_index.group(1)
        if table_name in preserved_tables:
            new_lines.append("# " + line)
            continue

    new_lines.append(line)

with open(file_path, 'w') as f:
    f.writelines(new_lines)

print("Finished processing upgrade and downgrade.")
