// Google OAuth Web Client ID — public by design (it's compiled into the JS
// bundle and visible to anyone). Lives in source rather than env because it's
// not a secret. The actual security boundary is the "Authorized JavaScript
// origins" list configured in Google Cloud Console + the audience check on
// our backend.
export const GOOGLE_CLIENT_ID =
  '1073035138993-bvba9dfi4pdr354p3d550bi95die8e83.apps.googleusercontent.com';
