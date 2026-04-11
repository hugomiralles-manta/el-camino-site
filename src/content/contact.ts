import { company } from './company';

/**
 * Contact channels — re-exported subset of company for convenient imports
 * in contact forms, footers, and info blocks.
 */
export const contact = {
  phone: company.phone,
  emails: company.emails,
  social: company.social,
  address: company.address,
} as const;
