# Career Mate AI - Wireframe Specifications

## Design System

### Color Palette
- **Background**: `#000000` (Pure black)
- **Surface**: `#18181B` (Zinc-900)
- **Borders**: `#27272A` (Zinc-800)
- **Text Primary**: `#FFFFFF` (White)
- **Text Secondary**: `#A1A1AA` (Zinc-400)
- **Accent Primary**: `#FFFFFF` (White buttons)
- **Accent Gradient**: Purple-500 to Blue-500

### Typography
- **Headlines**: Bold, 24-48px
- **Body**: Regular, 14-16px
- **Labels**: Medium, 12-14px
- **Captions**: Regular, 10-12px

### Spacing
- **Container Padding**: 16-32px
- **Card Padding**: 16-24px
- **Element Gap**: 8-16px
- **Section Gap**: 24-48px

---

## Screen 1: Home / Chat View

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ [Top Navigation Bar - Fixed]                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  [Message Area - Scrollable]                    │
│  ┌───────────────────────────────────────┐      │
│  │ [AI Avatar] [AI Message Bubble]       │      │
│  │             - Text content             │      │
│  │             - Agent label              │      │
│  └───────────────────────────────────────┘      │
│                                                 │
│  ┌───────────────────────────────────────┐      │
│  │             [User Message Bubble]      │      │
│  │             - Text content             │      │
│  └───────────────────────────────────────┘      │
│                                                 │
│  [Suggestion Chips - 2x2 Grid]                  │
│  ┌─────────┐ ┌─────────┐                       │
│  │[Icon] + │ │[Icon] + │                       │
│  │ Action  │ │ Action  │                       │
│  └─────────┘ └─────────┘                       │
│                                                 │
├─────────────────────────────────────────────────┤
│ [Input Bar - Fixed Bottom]                      │
│ [Input Field + Send Button]                     │
└─────────────────────────────────────────────────┘
```

### Component Specifications

#### AI Message Bubble
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Border Radius**: 16px
- **Padding**: 24px
- **Max Width**: 80% of container
- **Font**: 16px regular
- **Line Height**: 1.6

#### User Message Bubble
- **Background**: White
- **Text Color**: Black
- **Border Radius**: 16px
- **Padding**: 16px 24px
- **Max Width**: 70% of container
- **Alignment**: Right

#### Suggestion Chips
- **Size**: Flexible width, min 200px
- **Height**: 80px
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Hover**: Border changes to Zinc-700
- **Icon Container**: 32x32px, Zinc-800 background
- **Text**: 14px medium, White
- **Agent Label**: 12px, Zinc-600

#### Input Bar
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Border Radius**: 24px
- **Height**: 56px
- **Padding**: 8px 12px
- **Font**: 16px
- **Send Button**: 40x40px circle, White background, Black icon

### Interaction Rules
- **Enter key** sends message
- **Suggestion chips** auto-populate input
- **Messages** auto-scroll to bottom
- **Agent labels** always visible below AI responses
- **Loading state** shows typing indicator (3 dots animation)

---

## Screen 2: Job Explorer

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ [Top Navigation Bar - Fixed]                    │
├─────────────────────────────────────────────────┤
│ [Page Header]                                   │
│ - Title: "Job Explorer"                         │
│ - Subtitle                                      │
├─────────────────────────────────────────────────┤
│ [Search & Filter Bar]                           │
│ [Search Input] [Filter Button]                  │
├─────────────────────────────────────────────────┤
│ [Stage Filter Chips - Horizontal Scroll]        │
│ [All] [High Match] [Remote] [Recent]           │
├─────────────────────────────────────────────────┤
│ [Job Cards Grid - 3 Columns]                    │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│ │ [Match] │ │ [Match] │ │ [Match] │           │
│ │ Title   │ │ Title   │ │ Title   │           │
│ │ Company │ │ Company │ │ Company │           │
│ │ Details │ │ Details │ │ Details │           │
│ │ [Tags]  │ │ [Tags]  │ │ [Tags]  │           │
│ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────┘
```

### Component Specifications

#### Job Card
- **Size**: Flexible width, min 280px
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Border Radius**: 12px
- **Padding**: 20px
- **Hover**: Border Zinc-700, slight lift

**Header Section**:
- Match badge: Floating top-right
- Badge color based on score:
  - 90-100%: Green gradient
  - 80-89%: Blue gradient
  - 70-79%: Yellow gradient
  - <70%: Zinc

**Content Section**:
- Title: 18px semibold, white
- Company: 16px, Zinc-400
- Icon + Text details: 14px, Zinc-500

**Footer Section**:
- Tags: 12px, Zinc-800 background, Zinc-400 text
- Rounded: 6px
- Padding: 4px 8px

#### Stage Filter Chips
- **Height**: 48px
- **Padding**: 12px 16px
- **Border Left**: 4px colored (Cyan/Purple/Green/Yellow)
- **Active State**: Colored background with opacity
- **Badge**: Count in small circle

#### Search Bar
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Border Radius**: 12px
- **Height**: 48px
- **Icon**: Left-aligned, 20px
- **Padding Left**: 48px (to accommodate icon)

### Interaction Rules
- **Hover on card**: Border color changes, subtle shadow
- **Click card**: Navigate to Job Detail
- **Stage filter**: Instant client-side filtering
- **Search**: Debounced (300ms) filter
- **Empty state**: Shows illustration + message

---

## Screen 3: Job Detail

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ [Top Navigation Bar - Fixed]                    │
├─────────────────────────────────────────────────┤
│ [Back Button]                                   │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────┐ ┌─────────────────┐   │
│ │ MAIN CONTENT (2/3)  │ │ SIDEBAR (1/3)   │   │
│ │                     │ │                 │   │
│ │ [Header Card]       │ │ [Match Analysis]│   │
│ │ - Title             │ │ - Score bars    │   │
│ │ - Company           │ │ - Insights      │   │
│ │ - Quick Info Grid   │ │                 │   │
│ │                     │ │ [Quick Actions] │   │
│ │ [Description Card]  │ │ - Apply         │   │
│ │                     │ │ - Generate      │   │
│ │ [Requirements Card] │ │ - Save          │   │
│ │ - Checkmarks        │ │ - Analyze       │   │
│ │                     │ │                 │   │
│ │ [Benefits Card]     │ │ [Company Info]  │   │
│ │ - Badge chips       │ │ - Details       │   │
│ └─────────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Component Specifications

#### Header Card
- **Height**: Auto, min 200px
- **Background**: Zinc-900
- **Padding**: 24px

**Title Section**:
- Title: 32px bold
- Company: 20px, Zinc-400
- Match Badge: Gradient, 48x48px, top-right

**Quick Info Grid**: 2x2
- Each cell: Icon (40x40px Zinc-800 container) + Label + Value
- Spacing: 16px gap

#### Match Analysis Sidebar
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Padding**: 24px

**Score Bars**:
- Height: 8px
- Background: Zinc-800
- Fill: Gradient (color based on score)
- Label above: 14px
- Value right: 14px semibold
- Detail below: 12px Zinc-600

#### Requirements List
- Green checkmark icon: 20px
- Text: 16px, Zinc-400
- Gap: 12px between items
- Left alignment with icon

#### Quick Actions
- **Button Full Width**
- Primary: White background, Black text
- Secondary: Zinc-800 background, White text
- Height: 48px
- Border Radius: 8px
- Gap: 12px

### Interaction Rules
- **Back button**: Returns to Job Explorer
- **Apply button**: Opens application flow
- **Generate button**: Navigates to Generator with pre-filled data
- **Save button**: Adds to Application Tracker
- **Analyze button**: Requests deeper AI analysis

---

## Screen 4: Generator View

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ [Top Navigation Bar - Fixed]                    │
├─────────────────────────────────────────────────┤
│ [Tab Bar]                                       │
│ [Cover Letter] [Cold Email] [Interview Qs]     │
├─────────────────────────────────────────────────┤
│                                                 │
│ BEFORE GENERATION:                              │
│ ┌───────────────────────────────────────────┐  │
│ │ [Hero Section - Centered]                 │  │
│ │ - Subtitle                                │  │
│ │ - Large Title                             │  │
│ │ - Description                             │  │
│ └───────────────────────────────────────────┘  │
│                                                 │
│ ┌───────────────────────────────────────────┐  │
│ │ [Input Form Card]                         │  │
│ │ 1. Job Description                        │  │
│ │    [Textarea - Large]                     │  │
│ │                                           │  │
│ │ 2. Select Tone                            │  │
│ │    [Dropdown]                             │  │
│ │                                           │  │
│ │ [Generate Button - Full Width]           │  │
│ │ [Agent Info Text]                         │  │
│ └───────────────────────────────────────────┘  │
│                                                 │
│ AFTER GENERATION:                               │
│ ┌───────────────────────────────────────────┐  │
│ │ [Action Bar]                              │  │
│ │ [Copy] [Regenerate] [Download]           │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [Generated Content - White Paper]         │  │
│ │ [Formatted Text]                          │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [Quick Adjustments]                       │  │
│ │ [Shorter] [Longer] [Formal] [Examples]   │  │
│ └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Component Specifications

#### Tab Navigation
- **Height**: 48px
- **Active Tab**: White background, Black text, rounded top
- **Inactive Tab**: Transparent, Zinc-400 text
- **Hover**: Zinc-900 background
- **Border Bottom**: 1px Zinc-800

#### Input Form Card
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Padding**: 32px
- **Border Radius**: 12px
- **Max Width**: 800px, centered

**Textarea**:
- Height: 192px (12 lines)
- Background: Zinc-800
- Border: 1px Zinc-700
- Rounded: 12px
- Padding: 16px
- Font: 16px
- Resize: None

**Dropdown**:
- Height: 48px
- Background: Zinc-800
- Same styling as textarea

**Generate Button**:
- Height: 56px
- Background: White
- Text: Black, 16px semibold
- Icon: Sparkles, 20px
- Loading state: Spinning icon

#### Generated Content Area
- **Background**: White (paper effect)
- **Text**: Black
- **Padding**: 32px
- **Border Radius**: 8px
- **Font**: Serif for formal feel
- **Line Height**: 1.8

#### Quick Adjustment Buttons
- **Height**: 40px
- **Background**: Zinc-800
- **Hover**: Zinc-700
- **Border Radius**: 8px
- **Padding**: 12px 16px
- **Font**: 14px

### Interaction Rules
- **Tab switch**: Resets form, clears generated content
- **Generate**: Shows loading spinner for 2s, then result
- **Adjustment buttons**: Modify content, show subtle animation
- **Copy**: Shows toast notification
- **Download**: Triggers browser download as .txt or .docx

---

## Screen 5: Application Tracker

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ [Top Navigation Bar - Fixed]                    │
├─────────────────────────────────────────────────┤
│ [Page Header + Add Button]                      │
├─────────────────────────────────────────────────┤
│ [View Toggle]                                   │
│ [Board View] [List] [Calendar]                  │
├─────────────────────────────────────────────────┤
│ [Kanban Board - Horizontal Scroll]              │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐│
│ │SHORTLIST│ │APPLIED  │ │INTERVIEW│ │DONE    ││
│ │(Cyan)   │ │(Purple) │ │(Green)  │ │(Yellow)││
│ ├─────────┤ ├─────────┤ ├─────────┤ ├────────┤│
│ │[Card 1] │ │[Card 1] │ │[Card 1] │ │[Card 1]││
│ │[Card 2] │ │[Card 2] │ │         │ │        ││
│ │         │ │         │ │         │ │        ││
│ │[+ Add]  │ │[+ Add]  │ │[+ Add]  │ │[+ Add] ││
│ └─────────┘ └─────────┘ └─────────┘ └────────┘│
├─────────────────────────────────────────────────┤
│ [Stats Grid - 4 Columns]                        │
│ [Total] [Active] [Offers] [Avg Match]          │
└─────────────────────────────────────────────────┘
```

### Component Specifications

#### Stage Column
- **Width**: 320px
- **Min Width**: 300px
- **Gap**: 16px between columns

**Column Header**:
- Background: Zinc-900
- Border Left: 4px colored (by stage)
- Height: 64px
- Padding: 16px
- Rounded Top: 12px
- Count badge: 24px circle, Zinc-800

#### Job Card (Draggable)
- **Height**: Auto, min 140px
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Cursor**: Grab (grabbable)
- **Drag State**: Opacity 50%, cursor grabbing

**Card Structure**:
- Header: Title + More button
- Body: Location, Salary, Date icons + text
- Footer: Match score + Tasks count
- Divider: 1px Zinc-800

**Drag Drop Zone**:
- Highlight on hover: Border color changes
- Drop animation: Smooth transition

#### Add Card Button
- **Height**: 48px
- **Border**: 2px dashed Zinc-800
- **Hover**: Border Zinc-700, text Zinc-400
- **Icon**: Plus, 16px
- **Text**: 14px Zinc-600

#### Stats Cards
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Padding**: 24px
- **Border Radius**: 12px

**Layout**:
- Label: 14px Zinc-500
- Value: 32px bold White
- Icon: Optional, 24px

### Interaction Rules
- **Drag card**: Pick up, ghost follows cursor
- **Drop**: Animates to new position, backend update
- **Invalid drop**: Bounces back
- **Click card**: Opens Job Detail view
- **Add button**: Opens modal or inline form
- **Stats**: Update in real-time after stage changes

---

## Screen 6: Profile View

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ [Top Navigation Bar - Fixed]                    │
├─────────────────────────────────────────────────┤
│ [Page Header]                                   │
├─────────────────────────────────────────────────┤
│ [Tab Bar]                                       │
│ [Profile] [Documents]                           │
├─────────────────────────────────────────────────┤
│                                                 │
│ PROFILE TAB:                                    │
│ ┌───────────────────────────────────────────┐  │
│ │ [Basic Information Card]                  │  │
│ │ - 2 column grid                           │  │
│ │ - Edit button top-right                   │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [Skills Card]                             │  │
│ │ - Chip grid                               │  │
│ │ - Add button                              │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [Job Preferences Card]                    │  │
│ │ - 2 column grid                           │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [AI Profile Analysis Card - Gradient]     │  │
│ │ - Overall score bar                       │  │
│ │ - 3 column metric grid                    │  │
│ └───────────────────────────────────────────┘  │
│                                                 │
│ DOCUMENTS TAB:                                  │
│ ┌───────────────────────────────────────────┐  │
│ │ [Upload Section - 3 Cards]                │  │
│ │ [Create] [Import] [Template]              │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [My Documents Card]                       │  │
│ │ [Doc 1] [Doc 2] [Doc 3]...               │  │
│ └───────────────────────────────────────────┘  │
│ ┌───────────────────────────────────────────┐  │
│ │ [AI Optimization Card - Gradient]         │  │
│ │ - CTA button                              │  │
│ └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Component Specifications

#### Info Cards
- **Background**: Zinc-900
- **Border**: 1px Zinc-800
- **Padding**: 24px
- **Border Radius**: 12px
- **Gap**: 24px between cards

**Grid Layout** (2 columns):
- Label: 14px Zinc-500
- Value: 16px White
- Gap: 24px vertical, 32px horizontal

**Edit Button**:
- Size: 40x40px
- Background: Zinc-800
- Icon: 16px
- Hover: Zinc-700

#### Skill Chips
- **Height**: 40px
- **Background**: Zinc-800
- **Padding**: 12px 16px
- **Border Radius**: 8px
- **Checkmark**: Green, 16px
- **Delete Icon**: Appears on hover, 14px

#### Upload Cards (Documents Tab)
- **Size**: Equal width, flexible
- **Height**: 160px
- **Border**: 2px dashed Zinc-700
- **Hover**: Border Zinc-600, background Zinc-900
- **Icon Container**: 48x48px, colored background
- **Text**: Centered, 16px bold title, 14px description

#### Document List Item
- **Background**: Zinc-800
- **Border**: 1px Zinc-700
- **Height**: 72px
- **Border Radius**: 8px
- **Padding**: 16px

**Layout**: Horizontal flex
- Icon: 48x48px colored circle
- Info: Title (16px semibold) + Meta (14px Zinc-500)
- Actions: 4 icon buttons (32x32px each)

**Action Buttons**:
- Eye (view)
- Download
- Edit
- Trash (red on hover)

#### AI Analysis Cards
- **Background**: Gradient (Purple/Blue or Blue/Purple)
- **Border**: 1px colored with opacity
- **Padding**: 24px

**Score Bar**:
- Height: 8px
- Background: Zinc-800
- Fill: Gradient
- Animated on load

**Metric Grid**: 3 columns
- Large number: 28px bold, colored
- Small label: 12px Zinc-500

### Interaction Rules
- **Tab switch**: Instant content swap, no loading
- **Edit buttons**: Inline editing or modal
- **Skill add**: Opens dropdown or input field
- **Skill delete**: Confirmation toast, undo option
- **Upload**: Drag-drop or click to browse
- **Document actions**: Hover to reveal, click for action
- **AI Optimize**: Shows loading state, then results modal

---

## Navigation Bar (Global)

### Layout
```
┌─────────────────────────────────────────────────┐
│ [Logo] [Nav Items...]                [Profile] │
└─────────────────────────────────────────────────┘
```

### Specifications
- **Height**: 64px
- **Background**: Black with 50% opacity + backdrop blur
- **Border Bottom**: 1px Zinc-800
- **Position**: Fixed top
- **Z-Index**: 50

#### Logo
- **Icon**: 32x32px gradient circle (Purple to Blue)
- **Text**: 20px semibold "Career Mate AI"
- **Gap**: 8px

#### Nav Items
- **Height**: 40px
- **Padding**: 12px 16px
- **Border Radius**: 8px
- **Active**: White background, Black text
- **Inactive**: Zinc-400 text, hover Zinc-900 background
- **Icon**: 16px
- **Gap**: 8px between icon and text

### Interaction Rules
- **Active state**: Persists across navigation
- **Hover**: Smooth background transition (200ms)
- **Click**: Instant view change, no page reload
- **Mobile**: Collapses to hamburger menu (< 768px)

---

## Responsive Behavior

### Breakpoints
- **Mobile**: < 640px
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px

### Mobile Adaptations
- Navigation: Hamburger menu
- Job Grid: 1 column
- Job Detail: Sidebar below content
- Kanban: Horizontal scroll preserved
- Profile Grid: 1 column

### Tablet Adaptations
- Job Grid: 2 columns
- Chat: Narrower bubbles
- Generator: Full width
- Tracker: Horizontal scroll

### Desktop Optimizations
- Max width: 1440px (centered)
- Job Grid: 3 columns
- Side-by-side layouts: 2:1 ratio
- Hover effects enabled

---

## Animation & Transitions

### Standard Transitions
- Duration: 200ms
- Easing: ease-in-out
- Properties: background, border, opacity, transform

### Special Animations
- **Drag & Drop**: Scale 1.05 on pickup, ghost follows cursor
- **Loading States**: Spinning icon (360deg, 1s infinite)
- **Skeleton Loaders**: Shimmer effect (gradient animation)
- **Toasts**: Slide in from top, auto-dismiss 3s
- **Modals**: Fade + scale from center

### Microinteractions
- **Button Press**: Scale 0.98
- **Card Hover**: Translate Y -2px + shadow
- **Input Focus**: Border glow effect
- **Success**: Green checkmark bounce
- **Error**: Red shake animation

---

## Accessibility

### Keyboard Navigation
- **Tab Order**: Logical top-to-bottom, left-to-right
- **Focus Indicators**: 2px white outline, 2px offset
- **Shortcuts**: Ctrl/Cmd + K for search, Esc to close modals

### Screen Readers
- **ARIA Labels**: All interactive elements
- **Live Regions**: For dynamic content updates
- **Skip Links**: Jump to main content
- **Alt Text**: All decorative vs meaningful images

### Color Contrast
- **Text on Dark**: White (#FFF) on Black (#000) = 21:1
- **Secondary Text**: Zinc-400 (#A1A1AA) = 8.5:1
- **Accent Buttons**: White on Black = 21:1

---

## Loading & Error States

### Loading Patterns
- **Skeleton Screens**: For lists and cards
- **Spinners**: For buttons and inline actions
- **Progress Bars**: For long operations
- **Shimmer**: For text content loading

### Error States
- **Inline**: Red text below input
- **Toast**: Top-center notification
- **Empty State**: Illustration + message + CTA
- **Error Boundary**: Full screen fallback

### Success Feedback
- **Toast**: Green checkmark + message
- **Inline Icon**: Green check beside action
- **Animation**: Confetti for major actions (job offer)

---

## Conclusion

These wireframe specifications provide pixel-level detail for implementation while maintaining flexibility for engineering decisions. Each screen is designed to be:

1. **Self-documenting**: Clear visual hierarchy
2. **Consistent**: Reusable components and patterns
3. **Accessible**: WCAG 2.1 AA compliant
4. **Performant**: Optimized animations and transitions
5. **Responsive**: Mobile-first, progressively enhanced

All specifications align with the existing backend agent architecture and support incremental rollout.
