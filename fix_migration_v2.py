
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
    'wallets', 'warehouses', 'continents', 'battery_specs', 'battery_batches', 'countries',
    'roles', 'permissions', 'role_permissions', 'blacklist',
    'blacklisted_tokens', 'commission_configs', 'commission_logs', 'driver_profiles',
    'delivery_assignments', 'delivery_routes', 'route_stops',
    'dealer_settlements', 'regions', 'ticket_messages', 'battery_lifecycle_events', 
    'battery_transfers', 'cities', 'telemetics_data', 'zones', 'vendors', 'vendor_documents', 
    'station_slots', 'swap_sessions', 'user_roles',
    'dealer_applications', 'dealer_inventories', 'dealer_promotions', 'dealer_documents',
    'transactions', 'delivery_tracking', 'duplicate_accounts', 'ecommerce_orders',
    'order_items', 'wallet_withdrawal_requests', 'delivery_events',
    'return_requests', 'swap_requests', 'swap_histories',
    'ecommerce_order_items', 'field_visits', 'inventory_transactions', 'invoices',
    'purchases', 'refunds', 'return_inspections', 'device_commands',
    'settlements', 'stations', 'stationdowntime', 'station_images', 'favorite',
    'rentals', 'reviews', 'gps_tracking_log',
    'late_fees', 'promotion_usages', 'rental_extensions', 'rental_pauses', 'rentalevent',
    'swap_suggestions', 'late_fee_waivers'
}
# Added definitive list from scan. 
# admin_users and admin_user_roles are NOT in this list, so they will be created.

with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
block_level = 0
action = None 

# Check logic regex
create_table_start = re.compile(r"^\s*(?:#\s*)?op\.create_table\('(\w+)'")
create_index_start = re.compile(r"^\s*(?:#\s*)?op\.create_index")
drop_table_start = re.compile(r"^\s*(?:#\s*)?op\.drop_table\('(\w+)'")
drop_index_start = re.compile(r"^\s*(?:#\s*)?op\.drop_index")

def get_logic_line(line):
    s = line.strip()
    if s.startswith('#'):
        s = s[1:].strip()
    return s

for line in lines:
    logic_line = get_logic_line(line)
    open_p = logic_line.count('(')
    close_p = logic_line.count(')')
    
    if block_level == 0:
        target_table = None
        
        # CREATE TABLE
        m = create_table_start.match(line) or create_table_start.match(logic_line)
        if m:
            target_table = m.group(1)
            if target_table in preserved_tables:
                action = 'comment'
            else:
                action = 'keep'
        
        # CREATE INDEX
        if not target_table:
            if create_index_start.match(logic_line):
                found = False
                for pt in preserved_tables:
                    if f"'{pt}'" in logic_line or f'"{pt}"' in logic_line:
                        found = True
                        break
                if found:
                    action = 'comment'
                else:
                    action = 'keep'

        # DROP TABLE
        if not target_table:
            m = drop_table_start.match(logic_line)
            if m:
                target_table = m.group(1)
                if target_table in preserved_tables:
                    action = 'comment'
                else:
                    action = 'keep'

        # DROP INDEX
        if not target_table:
            if drop_index_start.match(logic_line):
                found = False
                for pt in preserved_tables:
                    if f"'{pt}'" in logic_line or f'"{pt}"' in logic_line:
                        found = True
                        break
                if found:
                    action = 'comment'
                else:
                    action = 'keep'

    current_line_balance = open_p - close_p
    
    if block_level == 0 and (open_p > 0 or close_p > 0) and action is not None:
        block_level += current_line_balance
        if action == 'comment':
            if not line.strip().startswith('#'):
                new_lines.append("# " + line)
            else:
                new_lines.append(line)
        else:
            # UNCOMMENT logic
            if line.strip().startswith('#'):
                 l_strip = line.lstrip()
                 if l_strip.startswith('# '):
                     indent = line[:line.find('#')]
                     content = l_strip[2:]
                     new_lines.append(indent + content)
                 elif l_strip.startswith('#'):
                     indent = line[:line.find('#')]
                     content = l_strip[1:]
                     new_lines.append(indent + content)
                 else:
                     new_lines.append(line)
            else:
                new_lines.append(line)
            
        if block_level <= 0:
            block_level = 0
            action = None
        continue

    if block_level > 0:
        block_level += current_line_balance
        if action == 'comment':
             if not line.strip().startswith('#'):
                new_lines.append("# " + line)
             else:
                new_lines.append(line)
        else:
             # UNCOMMENT logic
             if line.strip().startswith('#'):
                 l_strip = line.lstrip()
                 if l_strip.startswith('# '):
                     indent = line[:line.find('#')]
                     content = l_strip[2:]
                     new_lines.append(indent + content)
                 elif l_strip.startswith('#'):
                     indent = line[:line.find('#')]
                     content = l_strip[1:]
                     new_lines.append(indent + content)
                 else:
                     new_lines.append(line)
             else:
                 new_lines.append(line)
        
        if block_level <= 0:
            block_level = 0
            action = None
        continue

    new_lines.append(line)

with open(file_path, 'w') as f:
    f.writelines(new_lines)

print("Fixed with V3 logic (definitive list).")
