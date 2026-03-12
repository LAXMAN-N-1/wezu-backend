-- Fix stationstatus
ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'OFFLINE';
ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'operational';
ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'maintenance';
ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'closed';
ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'error';
ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'offline';

-- Fix usertype
ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'admin';
ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'customer';
ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'dealer';
ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'support_agent';
ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'logistics';

-- Fix userstatus
ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'active';
ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'suspended';
ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'pending_verification';
ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'deleted';

-- Fix batterystatus
ALTER TYPE batterystatus ADD VALUE IF NOT EXISTS 'available';
ALTER TYPE batterystatus ADD VALUE IF NOT EXISTS 'rented';
ALTER TYPE batterystatus ADD VALUE IF NOT EXISTS 'maintenance';
ALTER TYPE batterystatus ADD VALUE IF NOT EXISTS 'charging';
ALTER TYPE batterystatus ADD VALUE IF NOT EXISTS 'retired';

-- Fix rentalstatus
ALTER TYPE rentalstatus ADD VALUE IF NOT EXISTS 'active';
ALTER TYPE rentalstatus ADD VALUE IF NOT EXISTS 'completed';
ALTER TYPE rentalstatus ADD VALUE IF NOT EXISTS 'overdue';
ALTER TYPE rentalstatus ADD VALUE IF NOT EXISTS 'cancelled';
ALTER TYPE rentalstatus ADD VALUE IF NOT EXISTS 'pending_payment';

-- Fix batteryhealth
ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'good';
ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'fair';
ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'poor';
ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'critical';
ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'excellent';
ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'damaged';
