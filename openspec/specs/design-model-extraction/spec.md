# Design Model Extraction Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Extract data model interfaces from Figma sources for planner
The `design_prompt_section()` function SHALL extract TypeScript interface definitions from Figma source files (matching `*mockData*`, `*data*`, `*types*`, `*models*` patterns) and append them as a "## Design Data Model" section after the design snapshot content. This gives the planner concrete field names and types for embedding in scope descriptions.

#### Scenario: mockData.ts contains Product interface with shortDescription
- **WHEN** `sources/src__app__data__mockData.ts` exists and contains `export interface Product { id: number; name: string; shortDescription: string; ... }`
- **THEN** `design_prompt_section()` output SHALL include a "## Design Data Model" section containing the interface definition
- **AND** the planner SHALL be instructed to embed field names from these interfaces in scope descriptions

#### Scenario: No data model files in sources
- **WHEN** no source files match data/model/types patterns
- **THEN** no "## Design Data Model" section SHALL be appended (silent skip)

### Requirement: Planner embeds design model fields in scope descriptions
The planner planning rules SHALL instruct: "When a Design Data Model section is present, embed entity field names from the design interfaces in each change scope. For example, if the design defines `shortDescription` on Product, the scope for products-page MUST mention `shortDescription` explicitly so the implementing agent creates the correct schema field."

#### Scenario: Design model has shortDescription, planner generates scope
- **WHEN** Design Data Model shows `Product { name, shortDescription, description, price, ... }`
- **THEN** the products-page scope SHALL reference `shortDescription` (e.g., "ProductCard shows product.shortDescription below the name")

#### Scenario: Design model has variants, planner generates scope
- **WHEN** Design Data Model shows `Product { variants?: { [key: string]: string[] } }`
- **THEN** the relevant scope(s) SHALL reference variant attributes and their UI treatment

### Requirement: Seed data names extracted from mockData
When mockData source files contain array literals (e.g., `export const products: Product[] = [...]`), the planner section SHALL extract entity names from the data and instruct: "Seed data MUST use these exact entity names from the design: <list>."

#### Scenario: mockData has 6 product names
- **WHEN** mockData contains `{ name: "Wireless Earbuds Pro" }, { name: "USB-C Hub 7-in-1" }, ...`
- **THEN** the Design Data Model section SHALL list these names and instruct the planner to embed them in the seed data scope
