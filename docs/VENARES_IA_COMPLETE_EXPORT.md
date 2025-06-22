# VENARES IA - Exportação Completa do Sistema

## Informações Gerais
- **Nome**: VENARES IA - Sistema Inteligente de Análise Hormonal
- **Descrição**: Plataforma médica avançada com IA para análise hormonal e geração de condutas personalizadas
- **Tecnologia**: React + TypeScript + Express.js + PostgreSQL + OpenAI
- **Status**: Sistema funcional e validado clinicamente

## Estrutura de Arquivos Principal

### 1. Configurações de Projeto

#### package.json
```json
{
  "name": "rest-express",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "NODE_ENV=development tsx server/index.ts",
    "build": "npm run build:frontend && npm run build:backend",
    "build:frontend": "vite build",
    "build:backend": "esbuild server/index.ts --bundle --platform=node --outfile=dist/index.js --external:pg-native",
    "start": "node dist/index.js",
    "db:generate": "drizzle-kit generate",
    "db:push": "drizzle-kit push"
  },
  "dependencies": {
    "@anthropic-ai/sdk": "*",
    "@hookform/resolvers": "*",
    "@neondatabase/serverless": "*",
    "@radix-ui/react-*": "*",
    "@replit/vite-plugin-*": "*",
    "@stripe/react-stripe-js": "*",
    "@stripe/stripe-js": "*",
    "@tailwindcss/*": "*",
    "@tanstack/react-query": "*",
    "@types/*": "*",
    "@vitejs/plugin-react": "*",
    "autoprefixer": "*",
    "class-variance-authority": "*",
    "clsx": "*",
    "cmdk": "*",
    "connect-pg-simple": "*",
    "date-fns": "*",
    "drizzle-kit": "*",
    "drizzle-orm": "*",
    "drizzle-zod": "*",
    "embla-carousel-react": "*",
    "esbuild": "*",
    "express": "*",
    "express-session": "*",
    "framer-motion": "*",
    "input-otp": "*",
    "lucide-react": "*",
    "memorystore": "*",
    "next-themes": "*",
    "openai": "*",
    "passport": "*",
    "passport-local": "*",
    "postcss": "*",
    "react": "*",
    "react-day-picker": "*",
    "react-dom": "*",
    "react-hook-form": "*",
    "react-icons": "*",
    "react-resizable-panels": "*",
    "recharts": "*",
    "stripe": "*",
    "tailwind-merge": "*",
    "tailwindcss": "*",
    "tailwindcss-animate": "*",
    "tsx": "*",
    "tw-animate-css": "*",
    "typescript": "*",
    "vaul": "*",
    "vite": "*",
    "wouter": "*",
    "ws": "*",
    "zod": "*",
    "zod-validation-error": "*"
  }
}
```

#### tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./client/src/*"],
      "@assets/*": ["./attached_assets/*"],
      "@shared/*": ["./shared/*"]
    }
  },
  "include": ["client/src", "shared", "server"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

#### vite.config.ts
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname, "client"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "client/src"),
      "@assets": path.resolve(__dirname, "attached_assets"),
      "@shared": path.resolve(__dirname, "shared"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "dist/public"),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:5000",
    },
  },
});
```

#### tailwind.config.ts
```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./client/src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      animation: {
        'breathe': 'breathe 4s ease-in-out infinite',
        'breathe-slow': 'breathe 6s ease-in-out infinite',
        'gentle-float': 'gentle-float 6s ease-in-out infinite',
        'gentle-pulse': 'gentle-pulse 3s ease-in-out infinite',
        'gentle-bounce': 'gentle-bounce 2s ease-in-out infinite',
        'soothing-glow': 'soothing-glow 4s ease-in-out infinite',
        'gentle-glow': 'gentle-glow 3s ease-in-out infinite',
        'gentle-wave': 'gentle-wave 8s ease-in-out infinite',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.8' },
          '50%': { transform: 'scale(1.02)', opacity: '1' },
        },
        'gentle-float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'gentle-pulse': {
          '0%, 100%': { opacity: '0.8' },
          '50%': { opacity: '1' },
        },
        'gentle-bounce': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        'soothing-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(251, 191, 36, 0.3)' },
          '50%': { boxShadow: '0 0 30px rgba(251, 191, 36, 0.6)' },
        },
        'gentle-glow': {
          '0%, 100%': { boxShadow: '0 0 10px rgba(251, 191, 36, 0.2)' },
          '50%': { boxShadow: '0 0 20px rgba(251, 191, 36, 0.4)' },
        },
        'gentle-wave': {
          '0%, 100%': { transform: 'rotate(0deg)' },
          '25%': { transform: 'rotate(1deg)' },
          '75%': { transform: 'rotate(-1deg)' },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

### 2. Schema do Banco de Dados

#### shared/schema.ts
```typescript
import { pgTable, serial, text, integer, timestamp, boolean, numeric, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod";

// Users table
export const users = pgTable("users", {
  id: serial("id").primaryKey(),
  email: text("email").unique().notNull(),
  password: text("password").notNull(),
  firstName: text("first_name"),
  lastName: text("last_name"),
  crm: text("crm"),
  specialty: text("specialty"),
  phone: text("phone"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Patients table
export const patients = pgTable("patients", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").references(() => users.id).notNull(),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  email: text("email"),
  phone: text("phone"),
  dateOfBirth: text("date_of_birth"),
  gender: text("gender"),
  weight: numeric("weight"),
  height: numeric("height"),
  medicalHistory: text("medical_history"),
  currentMedications: text("current_medications"),
  allergies: text("allergies"),
  address: text("address"),
  city: text("city"),
  state: text("state"),
  zipCode: text("zip_code"),
  emergencyContact: text("emergency_contact"),
  emergencyPhone: text("emergency_phone"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Patient Priorities table
export const patientPriorities = pgTable("patient_priorities", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  priorityOrder: integer("priority_order").notNull(),
  priorityDescription: text("priority_description").notNull(),
  priorityCategory: text("priority_category"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Anamnesis Sessions table
export const anamnesisSessions = pgTable("anamnesis_sessions", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  sessionDate: timestamp("session_date").defaultNow(),
  chiefComplaint: text("chief_complaint"),
  historyOfPresentIllness: text("history_of_present_illness"),
  pastMedicalHistory: text("past_medical_history"),
  familyHistory: text("family_history"),
  socialHistory: text("social_history"),
  reviewOfSystems: text("review_of_systems"),
  physicalExamination: text("physical_examination"),
  vitalSigns: jsonb("vital_signs"),
  additionalNotes: text("additional_notes"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Bioimpedance Data table
export const bioimpedanceData = pgTable("bioimpedance_data", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  measurementDate: timestamp("measurement_date").defaultNow(),
  weight: numeric("weight"),
  height: numeric("height"),
  bmi: numeric("bmi"),
  bodyFatPercentage: numeric("body_fat_percentage"),
  musclePercentage: numeric("muscle_percentage"),
  visceralFat: numeric("visceral_fat"),
  basalMetabolicRate: numeric("basal_metabolic_rate"),
  bodyWaterPercentage: numeric("body_water_percentage"),
  boneMass: numeric("bone_mass"),
  proteinPercentage: numeric("protein_percentage"),
  notes: text("notes"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Lab Results table
export const labResults = pgTable("lab_results", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  testDate: timestamp("test_date").defaultNow(),
  testName: text("test_name").notNull(),
  testValue: text("test_value").notNull(),
  referenceRange: text("reference_range"),
  unit: text("unit"),
  isAbnormal: boolean("is_abnormal").default(false),
  notes: text("notes"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Clinical Cases table
export const clinicalCases = pgTable("clinical_cases", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  anamnesisSessionId: integer("anamnesis_session_id").references(() => anamnesisSessions.id),
  caseTitle: text("case_title").notNull(),
  caseDescription: text("case_description"),
  aiAnalysis: jsonb("ai_analysis"),
  conductRecommendations: jsonb("conduct_recommendations"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Suggested Conducts table
export const suggestedConducts = pgTable("suggested_conducts", {
  id: serial("id").primaryKey(),
  clinicalCaseId: integer("clinical_case_id").references(() => clinicalCases.id).notNull(),
  conductTitle: text("conduct_title").notNull(),
  conductDescription: text("conduct_description"),
  hormonalTreatment: jsonb("hormonal_treatment"),
  implantRecommendation: jsonb("implant_recommendation"),
  injectableMedications: jsonb("injectable_medications"),
  obesityTreatment: jsonb("obesity_treatment"),
  positivePoints: text("positive_points").array(),
  negativePoints: text("negative_points").array(),
  financialAnalysis: jsonb("financial_analysis"),
  isRecommended: boolean("is_recommended").default(true),
  confidenceScore: numeric("confidence_score"),
  reasoning: text("reasoning"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Treatment Outcomes table
export const treatmentOutcomes = pgTable("treatment_outcomes", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  conductId: integer("conduct_id").references(() => suggestedConducts.id),
  outcomeDate: timestamp("outcome_date").defaultNow(),
  treatmentResponse: text("treatment_response"),
  sideEffects: text("side_effects"),
  patientSatisfaction: integer("patient_satisfaction"),
  followUpNotes: text("follow_up_notes"),
  nextAppointment: timestamp("next_appointment"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Patient Scores table
export const patientScores = pgTable("patient_scores", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").references(() => patients.id).notNull(),
  evaluationDate: timestamp("evaluation_date").defaultNow(),
  energia: integer("energia"),
  libido: integer("libido"),
  musculatura: integer("musculatura"),
  emagrecimento: integer("emagrecimento"),
  cabeloPele: integer("cabelo_pele"),
  sangramento: integer("sangramento"),
  colica: integer("colica"),
  erecao: integer("erecao"),
  overallScore: numeric("overall_score"),
  notes: text("notes"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Medications table
export const medications = pgTable("medications", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  activeIngredient: text("active_ingredient"),
  concentration: text("concentration"),
  dosageForm: text("dosage_form"),
  manufacturer: text("manufacturer"),
  indication: text("indication"),
  contraindications: text("contraindications"),
  sideEffects: text("side_effects"),
  dosageInstructions: text("dosage_instructions"),
  preparationInstructions: text("preparation_instructions"),
  storageInstructions: text("storage_instructions"),
  price: numeric("price"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Medical Protocols table
export const medicalProtocols = pgTable("medical_protocols", {
  id: serial("id").primaryKey(),
  protocolName: text("protocol_name").notNull(),
  protocolType: text("protocol_type"),
  indications: text("indications"),
  contraindications: text("contraindications"),
  medications: text("medications").array(),
  dosageProtocol: text("dosage_protocol"),
  monitoringRequirements: text("monitoring_requirements"),
  expectedOutcomes: text("expected_outcomes"),
  duration: text("duration"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Drug Interactions table
export const drugInteractions = pgTable("drug_interactions", {
  id: serial("id").primaryKey(),
  medication1: text("medication1").notNull(),
  medication2: text("medication2").notNull(),
  interactionType: text("interaction_type"),
  severity: text("severity"),
  description: text("description"),
  clinicalManagement: text("clinical_management"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Lab References table
export const labReferences = pgTable("lab_references", {
  id: serial("id").primaryKey(),
  testName: text("test_name").notNull(),
  normalRangeMale: text("normal_range_male"),
  normalRangeFemale: text("normal_range_female"),
  unit: text("unit"),
  category: text("category"),
  clinicalSignificance: text("clinical_significance"),
  interpretation: text("interpretation"),
});

// Safety Protocols table
export const safetyProtocols = pgTable("safety_protocols", {
  id: serial("id").primaryKey(),
  protocolName: text("protocol_name").notNull(),
  protocolType: text("protocol_type"),
  preInfusionSteps: text("pre_infusion_steps").array(),
  duringInfusionSteps: text("during_infusion_steps").array(),
  postInfusionSteps: text("post_infusion_steps").array(),
  contraindications: text("contraindications").array(),
  requiredMaterials: text("required_materials").array(),
});

// Insert and Select schemas
export const insertUserSchema = createInsertSchema(users);
export const selectUserSchema = createSelectSchema(users);
export const insertPatientSchema = createInsertSchema(patients);
export const selectPatientSchema = createSelectSchema(patients);
export const insertPatientPrioritySchema = createInsertSchema(patientPriorities);
export const selectPatientPrioritySchema = createSelectSchema(patientPriorities);
export const insertAnamnesisSessionSchema = createInsertSchema(anamnesisSessions);
export const selectAnamnesisSessionSchema = createSelectSchema(anamnesisSessions);
export const insertBioimpedanceDataSchema = createInsertSchema(bioimpedanceData);
export const selectBioimpedanceDataSchema = createSelectSchema(bioimpedanceData);
export const insertLabResultSchema = createInsertSchema(labResults);
export const selectLabResultSchema = createSelectSchema(labResults);
export const insertClinicalCaseSchema = createInsertSchema(clinicalCases);
export const selectClinicalCaseSchema = createSelectSchema(clinicalCases);
export const insertSuggestedConductSchema = createInsertSchema(suggestedConducts);
export const selectSuggestedConductSchema = createSelectSchema(suggestedConducts);
export const insertTreatmentOutcomeSchema = createInsertSchema(treatmentOutcomes);
export const selectTreatmentOutcomeSchema = createSelectSchema(treatmentOutcomes);
export const insertPatientScoreSchema = createInsertSchema(patientScores);
export const selectPatientScoreSchema = createSelectSchema(patientScores);
export const insertMedicationSchema = createInsertSchema(medications);
export const selectMedicationSchema = createSelectSchema(medications);

// Type exports
export type User = typeof users.$inferSelect;
export type InsertUser = z.infer<typeof insertUserSchema>;
export type Patient = typeof patients.$inferSelect;
export type InsertPatient = z.infer<typeof insertPatientSchema>;
export type PatientPriority = typeof patientPriorities.$inferSelect;
export type InsertPatientPriority = z.infer<typeof insertPatientPrioritySchema>;
export type AnamnesisSession = typeof anamnesisSessions.$inferSelect;
export type InsertAnamnesisSession = z.infer<typeof insertAnamnesisSessionSchema>;
export type BioimpedanceData = typeof bioimpedanceData.$inferSelect;
export type InsertBioimpedanceData = z.infer<typeof insertBioimpedanceDataSchema>;
export type LabResult = typeof labResults.$inferSelect;
export type InsertLabResult = z.infer<typeof insertLabResultSchema>;
export type ClinicalCase = typeof clinicalCases.$inferSelect;
export type InsertClinicalCase = z.infer<typeof insertClinicalCaseSchema>;
export type SuggestedConduct = typeof suggestedConducts.$inferSelect;
export type InsertSuggestedConduct = z.infer<typeof insertSuggestedConductSchema>;
export type TreatmentOutcome = typeof treatmentOutcomes.$inferSelect;
export type InsertTreatmentOutcome = z.infer<typeof insertTreatmentOutcomeSchema>;
export type PatientScore = typeof patientScores.$inferSelect;
export type InsertPatientScore = z.infer<typeof insertPatientScoreSchema>;
export type Medication = typeof medications.$inferSelect;
export type InsertMedication = z.infer<typeof insertMedicationSchema>;
```

## Continua no próximo arquivo...