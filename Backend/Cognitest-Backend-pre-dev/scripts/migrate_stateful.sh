#!/bin/bash

# Migration script to add owasp_category and requires_stateful fields to TestCase model

cd /home/aneeshj/Downloads/Enmaz-Cognitest/backend

echo "Generating Prisma client with new schema..."
prisma generate

echo "Creating migration..."
prisma migrate dev --name add_stateful_testing_fields --create-only

echo "Applying migration..."
prisma migrate deploy

echo "Migration complete!"
echo ""
echo "Next steps:"
echo "1. Restart your backend server"
echo "2. Regenerate security tests to populate the new fields"
echo "3. Run tests to verify stateful testing works"
