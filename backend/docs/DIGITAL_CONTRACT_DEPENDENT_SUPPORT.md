# Digital Contract Dependent Support Implementation

## Overview
This document describes the implementation of dependent support in the digital contracts system, allowing contracts to be created and signed for dependent patients.

## Changes Made

### 1. Database Migration
- **File**: `backend/migrations/add_dependente_id_digital_contracts.sql`
- Added `dependente_id` column to `digital_contracts` table
- Created index for performance optimization

### 2. Backend Changes

#### 2.1 Models
- **File**: `backend/app/digital_contracts/models.py`
- Added `dependente_id` field to `DigitalContract` model
- Updated `ContractCreateRequest` to include optional `dependente_id`

#### 2.2 Service Layer
- **File**: `backend/app/digital_contracts/service.py`
- Modified `create_contract()` to:
  - Accept and store `dependente_id`
  - Automatically detect if odontogram belongs to a dependent
  - Fetch dependent information when rendering contracts
- Updated `_get_contract_data()` to include dependent details
- Modified `get_contract_for_client()` and `get_signed_contract_data()` to handle dependent contracts

#### 2.3 Router/API
- **File**: `backend/app/digital_contracts/router.py`
- Updated `ContractCreateRequest` model to include `dependente_id`
- Modified create contract endpoint to accept and pass `dependente_id`

#### 2.4 Templates
- **File**: `backend/app/digital_contracts/templates.py`
- Added `_prepare_dependent_header()` function to create dependent information header
- Added `_prepare_dependent_clause()` function to add dependent-specific clauses
- Modified `render_contract()` to include dependent sections when applicable
- All contract types now support dependent information automatically

### 3. Frontend Changes

#### 3.1 API Types
- **File**: `frontend/src/api/types/digitalContracts.ts`
- Updated `ContractCreateRequest` interface to include optional `dependente_id` field

#### 3.2 Components
- **File**: `frontend/src/pages/componentes/vendas/steps/ContractSignatureStep.tsx`
- Added `dependenteId` prop to component interface
- Updated component to receive and pass `dependenteId` when creating contracts

#### 3.3 Pages
- **File**: `frontend/src/pages/NovaVendaPage.tsx`
- Modified to pass `dependenteSelecionado?.dependente_id` to `ContractSignatureStep`

## How It Works

### Automatic Detection
When a contract is created, the system automatically:
1. Checks if the odontogram belongs to a dependent
2. Fetches dependent information if applicable
3. Includes dependent details in the contract

### Contract Display
For dependent contracts:
1. A yellow warning header is displayed indicating the contract is for a dependent
2. Dependent information (name, birth date, relationship) is shown
3. The responsible party (titular patient) information is included
4. A special clause is added explaining the contract is for dependent treatment

### Data Flow
1. Frontend selects a dependent in the sales flow
2. `dependente_id` is passed to `ContractSignatureStep`
3. Contract creation API receives `dependente_id`
4. Backend stores the ID and fetches dependent data
5. Template system automatically includes dependent sections

## Benefits
- Seamless integration with existing contract system
- All contract types automatically support dependents
- Clear visual indication of dependent contracts
- Proper legal documentation for dependent treatments
- No manual template modifications required

## Testing
To test the implementation:
1. Create a sale for a dependent
2. Navigate to the contract signature step
3. Verify the contract shows dependent information
4. Complete the signature process
5. Confirm the signed contract includes all dependent details
