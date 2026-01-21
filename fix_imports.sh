#!/bin/bash
# Fix all import errors in the backend

echo "Fixing import errors..."

# Fix kyc.py - Address import
sed -i '' 's/from app.models.user import User, Address/from app.models.user import User\nfrom app.models.address import Address/g' app/api/v1/kyc.py

echo "✅ Import fixes complete!"
echo "Testing imports..."
python -c "from app.main import app; print('✅ Server ready!')"
