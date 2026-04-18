import { useCallback, useEffect, useState } from 'react';
import { BsTools } from 'react-icons/bs';
import { FaArrowUp, FaCogs, FaFire, FaUsers } from 'react-icons/fa';
import { GiCarWheel, GiRaceCar } from 'react-icons/gi';
import { HiSparkles } from 'react-icons/hi';
import { Link } from 'react-router-dom';
import BuildListCard from '../components/buildLists/BuildListCard';
import LinkButton from '../components/buttons/LinkButton';
import { ErrorAlert } from '../components/common/Alerts';
import Card from '../components/common/Card';
import ImageWithPlaceholder from '../components/common/ImageWithPlaceholder';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { HOME_FEATURED_ITEMS_LIMIT } from '../constants';
import useApiRequest from '../hooks/UseApiRequest';
import { useAuth } from '../hooks/useAuth';
import {
  partManufacturersApi,
  buildListsApi,
  partsApi,
  retailersApi,
} from '../services/Api';
import type { BuildListReadWithVotes, PartReadWithVotes } from '../types/Api';

export default function HomePage() {
  const { user, isAuthenticated } = useAuth();
  const [featuredBuildLists, setFeaturedBuildLists] = useState<
    BuildListReadWithVotes[]
  >([]);
  const [popularParts, setPopularParts] = useState<PartReadWithVotes[]>([]);

  // Fetch featured build lists (top 6 by votes)
  const fetchFeaturedBuildListsFn = useCallback(
    () =>
      buildListsApi.getBuildListsWithVotes({
        limit: HOME_FEATURED_ITEMS_LIMIT,
        skip: 0,
      }),
    []
  );

  const {
    data: featuredBuildListsData,
    isLoading: isLoadingBuildLists,
    error: featuredBuildListsError,
    executeRequest: fetchFeaturedBuildLists,
  } = useApiRequest(fetchFeaturedBuildListsFn);

  // Fetch popular parts (top 6 by votes)
  const fetchPopularPartsFn = useCallback(
    () =>
      partsApi.getPartsWithVotes({
        limit: HOME_FEATURED_ITEMS_LIMIT,
        skip: 0,
      }),
    []
  );

  const {
    data: popularPartsData,
    isLoading: isLoadingParts,
    error: popularPartsError,
    executeRequest: fetchPopularParts,
  } = useApiRequest(fetchPopularPartsFn);

  // Stats bar: retailers and part_manufacturers count
  const fetchRetailersCountFn = useCallback(
    () => retailersApi.countRetailers(),
    []
  );
  const fetchPartManufacturersCountFn = useCallback(
    () => partManufacturersApi.countPartManufacturers(),
    []
  );
  const { data: retailersCountData, executeRequest: fetchRetailersCount } =
    useApiRequest(fetchRetailersCountFn);
  const {
    data: partManufacturersCountData,
    executeRequest: fetchPartManufacturersCount,
  } = useApiRequest(fetchPartManufacturersCountFn);

  useEffect(() => {
    void fetchFeaturedBuildLists();
    void fetchPopularParts();
    void fetchRetailersCount();
    void fetchPartManufacturersCount();
  }, [
    fetchFeaturedBuildLists,
    fetchPopularParts,
    fetchRetailersCount,
    fetchPartManufacturersCount,
  ]);

  useEffect(() => {
    if (featuredBuildListsData?.data) {
      // Sort by total votes (upvotes - downvotes) descending
      const sorted = [...featuredBuildListsData.data].sort(
        (a, b) => b.total_votes - a.total_votes
      );
      setFeaturedBuildLists(sorted);
    }
  }, [featuredBuildListsData]);

  useEffect(() => {
    if (popularPartsData?.data) {
      // Sort by total votes descending
      const sorted = [...popularPartsData.data].sort(
        (a, b) => b.total_votes - a.total_votes
      );
      setPopularParts(sorted);
    }
  }, [popularPartsData]);

  return (
    <div className="min-h-screen">
      {/* Landing-page ambient glow — fixed to viewport so it extends behind the ad gutters and persists while scrolling. */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl animate-float"></div>
        <div
          className="absolute bottom-0 left-0 w-96 h-96 bg-primary-400/10 rounded-full blur-3xl animate-float"
          style={{ animationDelay: '1.5s' }}
        ></div>
      </div>

      {/* Compact Hero Section */}
      <section className="relative py-16 px-4">
        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-3xl mx-auto animate-slideInUp">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-2xl animate-glow">
                <GiRaceCar className="text-white text-2xl" />
              </div>
            </div>

            <h1 className="text-4xl md:text-6xl font-bold mb-4 bg-gradient-to-r from-white via-primary-100 to-primary-300 bg-clip-text text-transparent">
              CarModPicker
            </h1>

            <p className="text-lg md:text-xl text-neutral-300 mb-6 leading-relaxed">
              Discover, plan, and share your car modifications with the
              community
            </p>

            {isAuthenticated && user ? (
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <LinkButton to="/builder" size="lg">
                  <BsTools className="mr-2" />
                  Create Build
                </LinkButton>
                <LinkButton to="/parts" variant="secondary" size="lg">
                  <FaCogs className="mr-2" />
                  Browse Parts
                </LinkButton>
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <LinkButton to="/register" size="lg">
                  <GiRaceCar className="mr-2" />
                  Get Started
                </LinkButton>
                <LinkButton to="/login" variant="secondary" size="lg">
                  Sign In
                </LinkButton>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Main Content Grid */}
      <div className="container mx-auto px-4 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Featured Build Lists - Takes 2 columns */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
                  <FaFire className="text-white text-lg" />
                </div>
                <h2 className="text-2xl md:text-3xl font-bold text-white">
                  Featured Builds
                </h2>
              </div>
              <Link
                to="/build-lists"
                className="text-primary-400 hover:text-primary-300 transition-colors text-sm font-semibold"
              >
                View All →
              </Link>
            </div>

            {isLoadingBuildLists ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner />
              </div>
            ) : featuredBuildListsError ? (
              <Card>
                <ErrorAlert
                  message={`Failed to load featured builds: ${featuredBuildListsError}`}
                />
              </Card>
            ) : featuredBuildLists.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {featuredBuildLists.map((buildList) => (
                  <BuildListCard key={buildList.id} buildList={buildList} />
                ))}
              </div>
            ) : (
              <Card>
                <p className="text-neutral-400 text-center py-8">
                  No featured builds yet. Be the first to create one!
                </p>
              </Card>
            )}
          </div>

          {/* Sidebar - Popular Parts & Quick Actions */}
          <div className="space-y-8">
            {/* Popular Parts */}
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-primary-600 rounded-lg flex items-center justify-center">
                  <HiSparkles className="text-white text-lg" />
                </div>
                <h2 className="text-2xl font-bold text-white">Popular Parts</h2>
              </div>

              {isLoadingParts ? (
                <div className="flex justify-center py-8">
                  <LoadingSpinner size="sm" />
                </div>
              ) : popularPartsError ? (
                <Card>
                  <ErrorAlert
                    message={`Failed to load popular parts: ${popularPartsError}`}
                  />
                </Card>
              ) : popularParts.length > 0 ? (
                <div className="space-y-4">
                  {popularParts.slice(0, 4).map((part) => (
                    <Link
                      key={part.id}
                      to={`/parts/${part.id}`}
                      className="block hover:no-underline"
                    >
                      <Card className="hover:border-primary-500 border-2 border-transparent transition-all duration-300 group">
                        <div className="flex gap-4">
                          <div className="flex-shrink-0">
                            <ImageWithPlaceholder
                              srcUrl={part.image_urls?.[0] ?? null}
                              altText={part.name}
                              imageClassName="w-16 h-16 object-cover rounded-lg"
                              containerClassName="w-16 h-16"
                              fallbackText="No img"
                            />
                          </div>
                          <div className="flex-grow min-w-0">
                            <h3 className="text-sm font-semibold text-white mb-1 group-hover:text-primary-400 transition-colors truncate">
                              {part.name}
                            </h3>
                            <div className="flex items-center gap-2 text-xs text-neutral-400">
                              <span className="flex items-center gap-1">
                                <FaArrowUp className="text-primary-400" />
                                {part.total_votes}
                              </span>
                            </div>
                          </div>
                        </div>
                      </Card>
                    </Link>
                  ))}
                  <Link
                    to="/parts"
                    className="block text-center text-primary-400 hover:text-primary-300 transition-colors text-sm font-semibold mt-4"
                  >
                    View All Parts →
                  </Link>
                </div>
              ) : (
                <Card>
                  <p className="text-neutral-400 text-center py-4 text-sm">
                    No parts yet
                  </p>
                </Card>
              )}
            </div>

            {/* Quick Actions */}
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-primary-600 rounded-lg flex items-center justify-center">
                  <GiCarWheel className="text-white text-lg" />
                </div>
                <h2 className="text-2xl font-bold text-white">Quick Actions</h2>
              </div>
              <div className="space-y-3">
                {isAuthenticated ? (
                  <>
                    <LinkButton
                      to="/builder"
                      variant="secondary"
                      className="w-full justify-start"
                    >
                      <BsTools className="mr-2" />
                      Create Build List
                    </LinkButton>
                    <LinkButton
                      to="/parts"
                      variant="secondary"
                      className="w-full justify-start"
                    >
                      <FaCogs className="mr-2" />
                      Add New Part
                    </LinkButton>
                    <LinkButton
                      to="/build-lists"
                      variant="outline"
                      className="w-full justify-start"
                    >
                      <FaUsers className="mr-2" />
                      Browse Builds
                    </LinkButton>
                  </>
                ) : (
                  <>
                    <LinkButton
                      to="/register"
                      variant="secondary"
                      className="w-full justify-start"
                    >
                      <GiRaceCar className="mr-2" />
                      Join Free
                    </LinkButton>
                    <LinkButton
                      to="/about"
                      variant="outline"
                      className="w-full justify-start"
                    >
                      Learn More
                    </LinkButton>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Stats Banner */}
        <div className="mt-12">
          <Card className="glass-card">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center max-w-4xl mx-auto">
              <div className="animate-slideInUp">
                <div className="text-3xl md:text-4xl font-bold text-primary-400 mb-2">
                  {featuredBuildListsData?.pagination?.total_items ?? '—'}
                </div>
                <div className="text-sm text-neutral-400">Build Lists</div>
              </div>
              <div
                className="animate-slideInUp"
                style={{ animationDelay: '0.1s' }}
              >
                <div className="text-3xl md:text-4xl font-bold text-primary-400 mb-2">
                  {popularPartsData?.pagination?.total_items ?? '—'}
                </div>
                <div className="text-sm text-neutral-400">Parts</div>
              </div>
              <div
                className="animate-slideInUp"
                style={{ animationDelay: '0.2s' }}
              >
                <div className="text-3xl md:text-4xl font-bold text-primary-400 mb-2">
                  {retailersCountData?.count ?? '—'}
                </div>
                <div className="text-sm text-neutral-400">Retailers</div>
              </div>
              <div
                className="animate-slideInUp"
                style={{ animationDelay: '0.3s' }}
              >
                <div className="text-3xl md:text-4xl font-bold text-primary-400 mb-2">
                  {partManufacturersCountData?.count ?? '—'}
                </div>
                <div className="text-sm text-neutral-400">
                  Part Manufacturers
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
