# Career Mate AI - System Design Documentation

## Overview
Career Mate AI is a comprehensive job search and career management platform powered by multi-agent AI systems. The UI is designed to seamlessly integrate with backend agents while providing an intuitive, modern user experience.

---

## User Personas

### 1. Student / Intern
- **Goals**: Find entry-level positions, internships, build first resume
- **Pain Points**: Limited experience, unclear job requirements
- **Key Features**: Resume templates, interview prep, career guidance

### 2. Junior Professional (1-3 years)
- **Goals**: Career growth, skill development, better opportunities
- **Pain Points**: Standing out in competitive market, career direction
- **Key Features**: Skill matching, market insights, profile optimization

### 3. Active Job Seeker
- **Goals**: Efficient job search, application tracking, interview success
- **Pain Points**: Managing multiple applications, time-consuming process
- **Key Features**: Application tracker, document generation, job matching

---

## Core User Journeys

### Journey 1: Discover Jobs
1. **Entry Point**: Chat interface or Job Explorer
2. **Actions**: Search/filter jobs, view match scores
3. **Backend**: Collector Agent fetches jobs, Matcher Agent calculates scores
4. **Output**: Sorted job listings with personalized match percentages

### Journey 2: Analyze an Offer
1. **Entry Point**: Job Detail view
2. **Actions**: View requirements, benefits, company info
3. **Backend**: Analyzer Agent evaluates fit, Stats Agent provides market data
4. **Output**: Detailed match breakdown, salary insights, skill gaps

### Journey 3: Match with Profile
1. **Entry Point**: Profile view or any job card
2. **Actions**: AI analyzes profile against job requirements
3. **Backend**: Matcher Agent compares skills, experience, preferences
4. **Output**: Match score with detailed breakdown by category

### Journey 4: Generate CV & Cover Letter
1. **Entry Point**: Generator view
2. **Actions**: Input job description, select tone, generate
3. **Backend**: Writer Agent creates personalized content using RAG
4. **Output**: Downloadable, editable document with quick adjustments

### Journey 5: Track Applications
1. **Entry Point**: Application Tracker
2. **Actions**: Drag-and-drop jobs between stages, add notes
3. **Backend**: Stats Agent monitors progress, sends reminders
4. **Output**: Kanban board with analytics and insights

### Journey 6: Ask Analytical Questions
1. **Entry Point**: Chat interface
2. **Actions**: Natural language queries about jobs, market, skills
3. **Backend**: RAG Agent retrieves context, appropriate agent responds
4. **Output**: Conversational answers with actionable insights

---

## Screen Map

### 1. Home / Chat (`/`)
- **Purpose**: Central AI assistant for all career queries
- **Components**: Message history, suggestion chips, input field
- **Interactions**: Natural language Q&A, quick actions

### 2. Job Explorer (`/jobs`)
- **Purpose**: Browse and filter job opportunities
- **Components**: Search bar, filter buttons, job cards grid, stage filters
- **Interactions**: Search, filter by match score/location/date, click to view details

### 3. Job Detail (`/jobs/:id`)
- **Purpose**: Deep dive into specific opportunity
- **Components**: Job info, requirements, benefits, match analysis, quick actions
- **Interactions**: Apply, generate cover letter, save to tracker, AI analysis

### 4. CV / Letter Generator (`/generator`)
- **Purpose**: AI-powered document creation
- **Components**: Input form, tone selector, generated output, editing tools
- **Tabs**: Cover Letter, Cold Email, Interview Questions
- **Interactions**: Input job description, generate, edit, download

### 5. Application Tracker (`/tracker`)
- **Purpose**: Kanban-style application management
- **Components**: Stage columns, job cards, stats dashboard
- **Stages**: Shortlist, Applied, Interviewing, Done
- **Interactions**: Drag-and-drop, add notes, view analytics

### 6. Profile / Documents (`/profile`)
- **Purpose**: Manage career profile and documents
- **Tabs**: Profile, Documents
- **Components**: Basic info, skills, preferences, document library
- **Interactions**: Edit profile, upload/create documents, AI optimization

---

## UI ↔ Backend Contracts

### Chat View
**Agents**: RAG, Collector, Analyzer, Matcher, Stats, Writer

#### Input to Backend:
```json
{
  "message": "string",
  "context": {
    "previousMessages": "array",
    "userProfile": "object"
  }
}
```

#### Output from Backend:
```json
{
  "response": "string",
  "agent": "string",
  "confidence": "number",
  "followUpActions": ["array"],
  "relatedJobs": ["array"] // optional
}
```

#### Interaction Rules:
- Chat is the primary interface for exploratory queries
- Agents are triggered based on intent classification
- System shows which agent is responding for transparency
- Suggestions appear based on conversation context

---

### Job Explorer
**Agents**: Collector, Matcher, Stats

#### Input to Backend:
```json
{
  "filters": {
    "location": "string",
    "salary": "range",
    "type": "string",
    "remote": "boolean"
  },
  "sortBy": "matchScore | date | salary",
  "userProfile": "object"
}
```

#### Output from Backend:
```json
{
  "jobs": [
    {
      "id": "string",
      "title": "string",
      "company": "string",
      "location": "string",
      "salary": "string",
      "matchScore": "number",
      "tags": ["array"],
      "postedDate": "date"
    }
  ],
  "totalCount": "number"
}
```

#### Interaction Rules:
- Jobs are fetched on mount with default filters
- Match scores calculated in real-time by Matcher Agent
- Filters trigger immediate re-fetch
- Stage filters are UI-only (no backend call)

---

### Job Detail
**Agents**: Analyzer, Matcher, Stats

#### Input to Backend:
```json
{
  "jobId": "string",
  "userProfile": "object",
  "requestAnalysis": "boolean"
}
```

#### Output from Backend:
```json
{
  "job": {
    "id": "string",
    "title": "string",
    "company": "string",
    "description": "string",
    "requirements": ["array"],
    "benefits": ["array"],
    "salary": "string",
    "location": "string"
  },
  "matchAnalysis": {
    "overallScore": "number",
    "skillsMatch": "number",
    "experienceMatch": "number",
    "locationMatch": "number",
    "salaryAlignment": "number",
    "gaps": ["array"],
    "strengths": ["array"]
  },
  "companyInsights": {
    "industry": "string",
    "size": "string",
    "rating": "number"
  }
}
```

#### Interaction Rules:
- Full analysis generated on page load
- "Analyze with AI" button triggers deeper analysis
- Quick actions button trigger specific agents (Writer for cover letter)

---

### Generator View
**Agents**: Writer, Matcher, RAG

#### Input to Backend:
```json
{
  "type": "cover-letter | cold-email | interview-questions",
  "jobDescription": "string",
  "tone": "professional | enthusiastic | creative | formal",
  "userProfile": "object",
  "jobId": "string" // optional
}
```

#### Output from Backend:
```json
{
  "content": "string",
  "metadata": {
    "wordCount": "number",
    "tone": "string",
    "matchedKeywords": ["array"]
  },
  "suggestions": ["array"] // editing suggestions
}
```

#### Interaction Rules:
- Generation triggered by "Generate" button only
- Takes 2-5 seconds (show loading state)
- Quick adjustment buttons send modification requests
- Users can regenerate unlimited times

---

### Application Tracker
**Agents**: Stats (monitoring), Collector (updates)

#### Input to Backend:
```json
{
  "action": "move | add | delete | update",
  "jobId": "string",
  "toStage": "wishlist | applied | interviewing | offer",
  "metadata": {
    "notes": "string",
    "appliedDate": "date"
  }
}
```

#### Output from Backend:
```json
{
  "success": "boolean",
  "applications": [
    {
      "id": "string",
      "jobId": "string",
      "stage": "string",
      "appliedDate": "date",
      "tasks": "number",
      "nextAction": "string"
    }
  ],
  "stats": {
    "totalApplications": "number",
    "activeInterviews": "number",
    "offersReceived": "number",
    "averageMatchScore": "number"
  }
}
```

#### Interaction Rules:
- Drag-and-drop triggers immediate backend update
- Stats refresh on any stage change
- "Add Job" opens modal, calls Collector agent if searching

---

### Profile View
**Agents**: Analyzer, Matcher, Stats

#### Input to Backend:
```json
{
  "action": "update | analyze",
  "profile": {
    "name": "string",
    "email": "string",
    "skills": ["array"],
    "experience": "string",
    "education": "string",
    "preferences": {
      "jobType": ["array"],
      "locations": ["array"],
      "salaryMin": "number"
    }
  }
}
```

#### Output from Backend:
```json
{
  "profile": "object",
  "analysis": {
    "overallScore": "number",
    "skillsMatch": "number",
    "completeness": "number",
    "marketFit": "number",
    "recommendations": ["array"]
  },
  "documents": [
    {
      "id": "string",
      "name": "string",
      "type": "resume | cover-letter | portfolio",
      "url": "string",
      "lastModified": "date"
    }
  ]
}
```

#### Interaction Rules:
- Profile edits auto-save after 2 seconds
- "Optimize" button triggers Matcher + Writer agents
- Document upload handled separately via file API

---

## Error Handling

### Missing Data
- Show placeholder UI with "Complete your profile" CTA
- Gracefully degrade features (e.g., no match scores if profile incomplete)
- Inline prompts to fill required fields

### Agent Failures
```json
{
  "error": true,
  "message": "Agent temporarily unavailable",
  "fallback": "object", // cached or default response
  "retryable": "boolean"
}
```
- Show error toast with retry option
- Use cached data when available
- Provide manual alternatives (e.g., template if Writer agent fails)

### Timeouts
- Show loading state max 10 seconds
- Auto-retry once, then show error
- Allow users to cancel long-running operations

---

## Constraints & Design Decisions

### Must Not Assume New Backend Logic
- All features map to existing agent capabilities
- No speculative features (e.g., video interviews, if not supported)
- UI gracefully handles agent unavailability

### Incremental Rollout
- Each screen is self-contained, can be deployed independently
- Agents can be swapped/updated without UI changes
- Feature flags for gradual rollout (e.g., disable Generator if Writer agent not ready)

### Avoid Unnecessary Screens
- Combined Profile + Documents into one view with tabs
- Job search integrated into Explorer (no separate screen)
- Settings embedded in Profile view

---

## Design for Evaluation

### Demo Support
- Pre-populated mock data for all screens
- Example conversations in Chat view
- Sample documents in Profile view
- Clear agent labels throughout UI

### Evaluation Results Display
- Agent names shown on all AI-generated content
- Processing time displayed for transparency
- Match score breakdowns show evaluation criteria
- Stats dashboard provides quantifiable metrics

### Defense Ready
- "How it works" tooltips explain each agent's role
- Clear data flow visualization in UI
- Backend contract documentation embedded
- Performance metrics visible (response times, success rates)

---

## Technical Implementation

### Tech Stack
- **Frontend**: React 18 + TypeScript
- **Styling**: Tailwind CSS v4
- **State Management**: React useState/useContext
- **Drag & Drop**: react-dnd
- **Icons**: lucide-react
- **Routing**: Client-side view state management

### Component Architecture
```
App.tsx (main router)
├── ChatView.tsx
├── JobExplorer.tsx
├── JobDetail.tsx
├── GeneratorView.tsx
├── ApplicationTracker.tsx
└── ProfileView.tsx
```

### Data Flow
1. User action → Component state update
2. Component → Backend API call (simulated)
3. Backend → Agent processing (simulated)
4. Agent → Response with metadata
5. Component → UI update with response

### Mock Data Strategy
- Realistic sample data for all entities
- Consistent IDs across views
- Simulated latency for realistic feel
- Agent names included in responses

---

## Key Features Summary

### AI-Powered
✅ Chat interface with multi-agent responses  
✅ Job matching with explainable scores  
✅ Document generation (cover letters, emails)  
✅ Interview question preparation  
✅ Profile optimization suggestions  

### User Experience
✅ Dark modern UI inspired by provided designs  
✅ Drag-and-drop application tracking  
✅ Quick actions and keyboard shortcuts  
✅ Responsive design (mobile-friendly)  
✅ Real-time search and filtering  

### Career Management
✅ Centralized job explorer  
✅ Application stage tracking  
✅ Document library  
✅ Profile strength analysis  
✅ Market insights and trends  

---

## Future Enhancements (Beyond Current Scope)

These features would require new backend capabilities:

- Real-time notifications (requires notification service)
- Calendar integration (requires calendar API)
- Video interview prep (requires video processing)
- Company reviews integration (requires review API)
- Salary negotiation assistant (requires specialized negotiation agent)
- Network analysis (requires LinkedIn/social graph API)

---

## Conclusion

This UI design respects the existing multi-agent backend architecture while providing an intuitive, modern interface for career management. Every interaction is mapped to specific agents, ensuring the UI can be incrementally wired to real backend services without major refactoring.

The design prioritizes:
1. **Clarity**: Users always know which agent is helping them
2. **Efficiency**: Quick actions reduce clicks and time
3. **Flexibility**: Modular design supports incremental rollout
4. **Transparency**: AI decisions are explainable and visible

Perfect for demo, defense, and production deployment.
