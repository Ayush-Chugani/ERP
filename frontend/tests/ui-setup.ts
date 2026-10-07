import '@testing-library/jest-dom/vitest';
import {configure} from '@testing-library/react';
// The four MUI suites share CI CPU; allow asynchronous rendering beyond 1 second.
configure({asyncUtilTimeout:3000});
