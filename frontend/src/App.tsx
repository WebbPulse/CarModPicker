import { lazy, Suspense } from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';

import AdBanner from './components/ads/AdBanner';
import ErrorBoundary from './components/common/ErrorBoundary';
import LoadingSpinner from './components/common/LoadingSpinner';
import Footer from './components/layout/globalFooter/Footer.tsx';
import Header from './components/layout/globalHeader/Header.tsx';
import EmailVerifiedRoute from './components/routes/EmailVerifiedRoute.tsx';
import GuestRoute from './components/routes/GuestRoute';
import ProtectedRoute from './components/routes/ProtectedRoute';

// Lazy load all page components for code splitting
const Home = lazy(() => import('./pages/Home.tsx'));
const Profile = lazy(() => import('./pages/Profile.tsx'));
const ForgotPassword = lazy(
  () => import('./pages/authentication/ForgotPassword.tsx')
);
const ForgotPasswordConfirm = lazy(
  () => import('./pages/authentication/ForgotPasswordConfirm.tsx')
);
const Login = lazy(() => import('./pages/authentication/Login.tsx'));
const Register = lazy(() => import('./pages/authentication/Register.tsx'));
const VerifyEmail = lazy(
  () => import('./pages/authentication/VerifyEmail.tsx')
);
const VerifyEmailConfirm = lazy(
  () => import('./pages/authentication/VerifyEmailConfirm.tsx')
);
const Builder = lazy(() => import('./pages/builder/Builder.tsx'));
const ViewCar = lazy(() => import('./pages/builder/ViewCar.tsx'));
const ViewUser = lazy(() => import('./pages/ViewUser.tsx'));
const About = lazy(() => import('./pages/About.tsx'));
const ContactUs = lazy(() => import('./pages/ContactUs.tsx'));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy.tsx'));
const Support = lazy(() => import('./pages/Support.tsx'));
const Search = lazy(() => import('./pages/Search.tsx'));
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard.tsx'));
const ReportReview = lazy(() => import('./pages/admin/ReportReview.tsx'));
const BugReportReview = lazy(() => import('./pages/admin/BugReportReview.tsx'));
const BugReport = lazy(() => import('./pages/BugReport.tsx'));
const UserManagement = lazy(() => import('./pages/admin/UserManagement.tsx'));
const BuildListsCatalog = lazy(
  () => import('./pages/buildLists/BuildListsCatalog.tsx')
);
const ViewBuildLog = lazy(() => import('./pages/buildLists/ViewBuildLog.tsx'));
const ViewBuildList = lazy(() => import('./pages/builder/ViewBuildlist.tsx'));
const ViewGlobalPart = lazy(() => import('./pages/builder/ViewGlobalPart.tsx'));
const EditGlobalPart = lazy(
  () => import('./pages/globalParts/EditGlobalPart.tsx')
);
const GlobalPartsCatalog = lazy(
  () => import('./pages/globalParts/GlobalPartsCatalog.tsx')
);
const UserGlobalParts = lazy(
  () => import('./pages/globalParts/UserGlobalParts.tsx')
);
function App() {
  const location = useLocation();

  return (
    <ErrorBoundary>
      <div className="flex flex-col min-h-screen bg-gradient-to-br from-neutral-900 via-neutral-800 to-neutral-900">
        {/* Background Pattern */}
        <div className="fixed inset-0 opacity-5">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
                               radial-gradient(circle at 75% 75%, rgba(139, 92, 246, 0.1) 0%, transparent 50%)`,
            }}
          ></div>
        </div>

        <Header />

        <main className="flex-grow relative z-10 flex w-full">
          {/* Left margin ad - new ad on each route (key forces remount) */}
          <AdBanner
            key={`left-${location.pathname}`}
            side="left"
            slotId={
              import.meta.env.VITE_ADSENSE_SLOT_LEFT as string | undefined
            }
          />

          <div className="main-content flex-1 min-w-0 w-full">
            <Suspense
              fallback={
                <div className="container mx-auto px-4 py-20">
                  <LoadingSpinner size="lg" text="Loading page..." />
                </div>
              }
            >
              <Routes>
                {/* Public Routes */}
                <Route path="/" element={<Home />} />

                {/* Guest Routes (redirect if logged in) */}
                <Route element={<GuestRoute />}>
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                </Route>

                {/* Public Info Pages */}
                <Route path="/about" element={<About />} />
                <Route path="/privacy-policy" element={<PrivacyPolicy />} />
                <Route path="/contact-us" element={<ContactUs />} />
                <Route path="/support" element={<Support />} />
                <Route path="/bug-report" element={<BugReport />} />
                <Route path="/search" element={<Search />} />
                <Route path="/user/:userId" element={<ViewUser />} />
                <Route
                  path="/verify-email/confirm"
                  element={<VerifyEmailConfirm />}
                />
                <Route
                  path="/forgot-password/confirm"
                  element={<ForgotPasswordConfirm />}
                />
                <Route path="/cars/:carId" element={<ViewCar />} />
                <Route
                  path="/build-lists/:buildListId"
                  element={<ViewBuildList />}
                />
                <Route
                  path="/build-lists/:buildListId/build-log"
                  element={<ViewBuildLog />}
                />
                <Route path="/build-lists" element={<BuildListsCatalog />} />
                <Route
                  path="/global-parts/:partId/edit"
                  element={<EditGlobalPart />}
                />
                <Route
                  path="/global-parts/:partId"
                  element={<ViewGlobalPart />}
                />
                <Route path="/global-parts" element={<GlobalPartsCatalog />} />

                {/* Protected Routes */}
                <Route element={<ProtectedRoute />}>
                  <Route path="/verify-email" element={<VerifyEmail />} />
                  <Route element={<EmailVerifiedRoute />}>
                    <Route path="/profile" element={<Profile />} />
                    <Route path="/builder" element={<Builder />} />
                    <Route
                      path="/my-global-parts"
                      element={<UserGlobalParts />}
                    />
                  </Route>
                </Route>

                {/* Admin Routes */}
                <Route path="/admin" element={<AdminDashboard />} />
                <Route path="/admin/reports" element={<ReportReview />} />
                <Route
                  path="/admin/bug-reports"
                  element={<BugReportReview />}
                />
                <Route path="/admin/users" element={<UserManagement />} />

                {/* 404 Catch-all - Must be last */}
                <Route
                  path="*"
                  element={
                    <div className="container mx-auto px-4 py-20 text-center">
                      <div className="glass-card rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">
                        <h1 className="text-4xl font-bold text-gradient mb-4">
                          404
                        </h1>
                        <p className="text-neutral-400 mb-6">Page not found</p>
                        <a
                          href="/"
                          className="btn-primary inline-flex items-center"
                        >
                          Go Home
                        </a>
                      </div>
                    </div>
                  }
                />
              </Routes>
            </Suspense>
          </div>

          {/* Right margin ad - new ad on each route (key forces remount) */}
          <AdBanner
            key={`right-${location.pathname}`}
            side="right"
            slotId={
              import.meta.env.VITE_ADSENSE_SLOT_RIGHT as string | undefined
            }
          />
        </main>

        <Footer />
      </div>
    </ErrorBoundary>
  );
}

export default App;
