import type { ComponentType } from 'react';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import AccountBalance from '@mui/icons-material/AccountBalanceOutlined';
import Apartment from '@mui/icons-material/ApartmentOutlined';
import AppRegistration from '@mui/icons-material/AppRegistrationOutlined';
import Article from '@mui/icons-material/ArticleOutlined';
import Badge from '@mui/icons-material/BadgeOutlined';
import BusinessCenter from '@mui/icons-material/BusinessCenterOutlined';
import CalendarMonth from '@mui/icons-material/CalendarMonthOutlined';
import Campaign from '@mui/icons-material/CampaignOutlined';
import Dashboard from '@mui/icons-material/DashboardOutlined';
import Dataset from '@mui/icons-material/DatasetOutlined';
import Description from '@mui/icons-material/DescriptionOutlined';
import EmojiEvents from '@mui/icons-material/EmojiEventsOutlined';
import Event from '@mui/icons-material/EventOutlined';
import FolderSpecial from '@mui/icons-material/FolderSpecialOutlined';
import Gavel from '@mui/icons-material/GavelOutlined';
import Grading from '@mui/icons-material/GradingOutlined';
import Groups from '@mui/icons-material/GroupsOutlined';
import HowToReg from '@mui/icons-material/HowToRegOutlined';
import MenuBook from '@mui/icons-material/MenuBookOutlined';
import Paid from '@mui/icons-material/PaidOutlined';
import PersonAdd from '@mui/icons-material/PersonAddAltOutlined';
import RateReview from '@mui/icons-material/RateReviewOutlined';
import School from '@mui/icons-material/SchoolOutlined';
import Science from '@mui/icons-material/ScienceOutlined';
import Schedule from '@mui/icons-material/ScheduleOutlined';
import Security from '@mui/icons-material/AdminPanelSettingsOutlined';
import SportsSoccer from '@mui/icons-material/SportsSoccerOutlined';
import SupportAgent from '@mui/icons-material/SupportAgentOutlined';
import Topic from '@mui/icons-material/TopicOutlined';
import Workspaces from '@mui/icons-material/WorkspacesOutlined';
import type { ResourceSummary } from '../api/types';

export type Icon = ComponentType<SvgIconProps>;

export type Workspace = { key: string; title: string; blurb: string; icon: Icon };

/** The areas people think in. Resources are placed in one of these from the module/table the API reports. */
export const WORKSPACES: Workspace[] = [
  { key: 'academics', title: 'Academics', blurb: 'Calendar, curriculum, timetable, attendance, registration and assessments', icon: School },
  { key: 'students', title: 'Students', blurb: 'Admissions, student records and the student lifecycle', icon: Groups },
  { key: 'staff', title: 'Staff', blurb: 'Employees, assignments, qualifications and HR records', icon: Badge },
  { key: 'research', title: 'Research & records', blurb: 'Publications, projects, awards, memberships and evidence', icon: Science },
  { key: 'engage', title: 'Support & communication', blurb: 'Mentoring, grievances, feedback and announcements', icon: SupportAgent },
  { key: 'documents', title: 'Documents', blurb: 'Certificates, student documents and exits', icon: Description },
  { key: 'organization', title: 'Organization', blurb: 'Institutions, campuses, departments and reference data', icon: Apartment },
];

const MODULE_WORKSPACE: Record<string, string> = {
  calendar: 'academics', curriculum: 'academics', timetable: 'academics', attendance: 'academics',
  registration: 'academics', assessments: 'academics',
  admissions: 'students', people: 'students',
  hr: 'staff', 'staff-profile': 'staff',
  'research-publications': 'research', 'research-proposals': 'research', 'funded-projects': 'research',
  consultancy: 'research', awards: 'research', conferences: 'research', 'faculty-internships': 'research',
  'professional-contributions': 'research', 'professional-memberships': 'research', cocurricular: 'research',
  extracurricular: 'research', 'staff-activities': 'research', evidence: 'research',
  support: 'engage', communication: 'engage', feedback: 'engage',
  documents: 'documents',
  organization: 'organization', reference: 'organization', tenancy: 'organization', security: 'organization',
};

export const workspaceOf = (r: Pick<ResourceSummary, 'module' | 'table'>): string => {
  if (r.module === 'people') return r.table.startsWith('student') ? 'students' : 'staff';
  return MODULE_WORKSPACE[r.module] ?? 'organization';
};

const MODULE_ICON: Record<string, Icon> = {
  calendar: CalendarMonth, curriculum: MenuBook, timetable: Schedule, attendance: HowToReg, registration: AppRegistration,
  assessments: Grading, admissions: PersonAdd, people: Groups, hr: Badge, 'staff-profile': Badge,
  'research-publications': Science, 'research-proposals': Science, 'funded-projects': Paid, consultancy: BusinessCenter,
  awards: EmojiEvents, conferences: Event, 'faculty-internships': BusinessCenter, 'professional-contributions': Topic,
  'professional-memberships': Badge, cocurricular: SportsSoccer, extracurricular: SportsSoccer, 'staff-activities': Topic,
  evidence: FolderSpecial, support: SupportAgent, communication: Campaign, feedback: RateReview, documents: Description,
  organization: Apartment, reference: Dataset, tenancy: AccountBalance, security: Security,
};

export const iconForModule = (module: string): Icon => MODULE_ICON[module] ?? Article;

export function iconForResource(r: Pick<ResourceSummary, 'module' | 'table'>): Icon {
  const t = r.table;
  if (t.startsWith('student')) return Groups;
  if (t.startsWith('employee')) return Badge;
  if (t.includes('grievance')) return Gavel;
  if (t.includes('certificate')) return Description;
  if (t.includes('announcement')) return Campaign;
  if (t.includes('attendance')) return HowToReg;
  if (t.includes('session') || t.includes('timetable')) return Schedule;
  if (t.includes('result') || t.includes('mark') || t.includes('assessment') || t.includes('grade')) return Grading;
  return iconForModule(r.module);
}

/** Lookup / configuration tables are kept out of the everyday menu and grouped under "Setup" on the area page. */
const SETUP = /(_status|_type|_types|_category|_level|_policy|_scale|_rule|_source|_mode|_agency|_body|_organization|_institution|_tag|_group)$|^(blood_group|gender|religion|caste|sub_caste|country|state|designation|participation_level|time_slot|building|room|semester|document_type|certificate_type|announcement_type|approval_status|verification_status|attendance_status|confidentiality_level|research_status|funding_type|funding_agency|journal|publisher|indexing_agency|metric_type|organizer|qualification_level|role_type|study_mode|university)$/;
export const isSetup = (r: Pick<ResourceSummary, 'table'>): boolean => SETUP.test(r.table);

export const HomeIcon = Dashboard;
export const AllIcon = Workspaces;
