import type { AuthUser } from '../lib/auth-context';
import { permitted as referencePermitted, resources as referenceResources } from '../features/common-reference/resources';

/**
 * Single source of truth for navigation + routing.
 * `prefix` is the backend mount under /api/v1 (see backend/config/urls.py).
 * `path` is the frontend hash route (single HashRouter at app root).
 */
export type NavItem = {
  path: string;
  title: string;
  short: string;
  group: string;
  prefix: string;
  visible: (user: AuthUser) => boolean;
};

const always = () => true;

/**
 * Show an entry when the user holds a Django permission under one of `apps`, or an IAM
 * role grant on one of `modules`. Navigation only: every endpoint still enforces its own check.
 */
const access =
  (apps: string[], modules: string[]) =>
  (user: AuthUser): boolean =>
    user.is_superuser ||
    apps.some((a) => user.permissions.some((perm) => perm.startsWith(`${a}.`))) ||
    modules.some((m) => (user.access_modules ?? []).includes(m));

export const NAV_GROUPS = ['Workspace', 'Academic core', 'Student lifecycle', 'Staff & research', 'Platform'] as const;

export const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard', title: 'Dashboard', short: 'Dashboard', group: 'Workspace', prefix: '', visible: always },
  { path: '/organization', title: 'Organization structure', short: 'Organization', group: 'Workspace', prefix: 'organization', visible: access(['organization'], ['INSTITUTION']) },
  { path: '/reference', title: 'Common reference data', short: 'Reference data', group: 'Workspace', prefix: 'common_reference', visible: (u) => referenceResources.some((r) => referencePermitted(u, r, 'view')) },
  { path: '/people', title: 'Students and staff', short: 'People', group: 'Academic core', prefix: 'people_master', visible: access(['people_master'], []) },
  { path: '/curriculum', title: 'Curriculum catalog', short: 'Curriculum', group: 'Academic core', prefix: 'curriculum_catalog', visible: access(['curriculum_catalog'], ['CURRICULUM']) },
  { path: '/calendar', title: 'Academic calendar', short: 'Calendar', group: 'Academic core', prefix: 'academic_calendar', visible: access(['academic_calendar'], ['ACADEMIC_CALENDAR']) },
  { path: '/timetable', title: 'Teaching and timetable', short: 'Timetable', group: 'Academic core', prefix: 'teaching_timetable', visible: access(['teaching_timetable'], ['TIMETABLE', 'TEACHING']) },
  { path: '/attendance', title: 'Attendance and lesson plans', short: 'Attendance', group: 'Academic core', prefix: 'attendance_lesson_plan', visible: access(['attendance_lesson_plan'], ['ATTENDANCE']) },
  { path: '/registration', title: 'Term registration', short: 'Registration', group: 'Academic core', prefix: 'term_registration', visible: (u: AuthUser) => access(['term_registration'], [])(u) || (u.groups ?? []).includes('Student') },
  { path: '/assessments', title: 'Assessment and results', short: 'Assessments', group: 'Academic core', prefix: 'assessments_results', visible: access(['assessments_results'], ['ASSESSMENT', 'RESULT']) },
  { path: '/admissions', title: 'Admissions and enrolment', short: 'Admissions', group: 'Student lifecycle', prefix: 'admission_enrolment', visible: access(['admission_enrolment'], []) },
  { path: '/support', title: 'Student support', short: 'Support', group: 'Student lifecycle', prefix: 'student_support', visible: access(['student_support'], ['MENTORING', 'GRIEVANCE']) },
  { path: '/feedback', title: 'Feedback', short: 'Feedback', group: 'Student lifecycle', prefix: 'feedback', visible: access(['feedback'], ['FEEDBACK']) },
  { path: '/documents', title: 'Documents and exits', short: 'Documents', group: 'Student lifecycle', prefix: 'documents_exit', visible: access(['documents_exit'], ['DOCUMENT']) },
  { path: '/communication', title: 'Communication', short: 'Communication', group: 'Student lifecycle', prefix: 'communication', visible: access(['communication'], ['COMMUNICATION']) },
  { path: '/evidence', title: 'Centralized evidence', short: 'Evidence', group: 'Staff & research', prefix: 'evidence', visible: access([], ['EVIDENCE']) },
  { path: '/awards', title: 'Awards', short: 'Awards', group: 'Staff & research', prefix: 'awards', visible: access([], ['AWARDS']) },
  { path: '/conferences', title: 'Conferences', short: 'Conferences', group: 'Staff & research', prefix: 'conferences', visible: access([], ['CONFERENCES']) },
  { path: '/consultancy', title: 'Consultancy', short: 'Consultancy', group: 'Staff & research', prefix: 'consultancy', visible: access([], ['CONSULTANCY']) },
  { path: '/funded-projects', title: 'Funded projects', short: 'Funded projects', group: 'Staff & research', prefix: 'funded_projects', visible: access([], ['FUNDED_PROJECTS']) },
  { path: '/research-proposals', title: 'Research proposals', short: 'Proposals', group: 'Staff & research', prefix: 'research_proposals', visible: access([], ['RESEARCH_PROPOSALS']) },
  { path: '/faculty-internships', title: 'Faculty internships', short: 'Internships', group: 'Staff & research', prefix: 'faculty_internships', visible: access([], ['FACULTY_INTERNSHIPS']) },
  { path: '/professional-contributions', title: 'Professional contributions', short: 'Contributions', group: 'Staff & research', prefix: 'professional_contributions', visible: access([], ['PROFESSIONAL_CONTRIBUTIONS']) },
  { path: '/professional-memberships', title: 'Professional memberships', short: 'Memberships', group: 'Staff & research', prefix: 'professional_memberships', visible: access([], ['PROFESSIONAL_MEMBERSHIPS']) },
  { path: '/cocurricular', title: 'Co-curricular', short: 'Co-curricular', group: 'Staff & research', prefix: 'cocurricular', visible: access([], ['COCURRICULAR']) },
  { path: '/extracurricular', title: 'Extra-curricular', short: 'Extra-curricular', group: 'Staff & research', prefix: 'extracurricular', visible: access([], ['EXTRACURRICULAR']) },
  { path: '/security', title: 'Identity and access', short: 'Security', group: 'Platform', prefix: 'identity_access', visible: access(['identity_access'], ['IAM']) },
];

export function visibleNav(user: AuthUser | null): NavItem[] {
  if (!user) return [];
  return NAV_ITEMS.filter((item) => {
    try {
      return item.visible(user);
    } catch {
      return true;
    }
  });
}
