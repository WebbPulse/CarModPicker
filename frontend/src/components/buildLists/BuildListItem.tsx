import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { buildListVotesApi, carsApi } from '../../services/Api';
import type {
  BuildListRead,
  BuildListReadWithVotes,
  CarRead,
  VoteSummary,
} from '../../types/Api';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import VoteButtons from '../globalParts/VoteButtons';

interface BuildListItemProps {
  buildList: BuildListRead | BuildListReadWithVotes;
  showVoteButtons?: boolean;
  onVoteUpdate?: (
    buildListId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => void;
}

const BuildListItem: React.FC<BuildListItemProps> = ({
  buildList,
  showVoteButtons = false,
  onVoteUpdate,
}) => {
  const hasVoteData = 'upvotes' in buildList && 'downvotes' in buildList;
  const buildListWithVotes = hasVoteData
    ? (buildList)
    : null;

  // Fetch vote summary if vote data is not available
  const [voteSummary, setVoteSummary] = useState<VoteSummary | null>(null);
  const [isLoadingVotes, setIsLoadingVotes] = useState(false);
  
  // Fetch car information if car_id is available
  const [carInfo, setCarInfo] = useState<CarRead | null>(null);
  const [isLoadingCar, setIsLoadingCar] = useState(false);

  useEffect(() => {
    // Fetch vote summary if vote data is not available
    // This ensures we have accurate counts even when the buildList object doesn't include vote data
    if (!hasVoteData && !isLoadingVotes && !voteSummary) {
      setIsLoadingVotes(true);
      buildListVotesApi
        .getVoteSummary(buildList.id)
        .then((response) => {
          // API returns AxiosResponse<VoteSummary>, so response.data is the VoteSummary
          setVoteSummary(response.data);
          setIsLoadingVotes(false);
        })
        .catch(() => {
          setIsLoadingVotes(false);
        });
    }
  }, [buildList.id, hasVoteData, isLoadingVotes, voteSummary]);

  useEffect(() => {
    // Fetch car information if car_id is available
    if (buildList.car_id && !isLoadingCar && !carInfo) {
      setIsLoadingCar(true);
      carsApi
        .getCar(buildList.car_id)
        .then((response) => {
          setCarInfo(response.data);
          setIsLoadingCar(false);
        })
        .catch(() => {
          setIsLoadingCar(false);
        });
    }
  }, [buildList.car_id, isLoadingCar, carInfo]);

  // Determine vote data from available sources
  // Prefer voteSummary (freshly fetched) over buildListWithVotes (may be stale)
  const upvotes = voteSummary?.upvotes ?? buildListWithVotes?.upvotes ?? 0;
  const downvotes =
    voteSummary?.downvotes ?? buildListWithVotes?.downvotes ?? 0;
  const userVote =
    voteSummary?.user_vote ?? buildListWithVotes?.user_vote ?? null;
  
  // Calculate net vote score (upvotes - downvotes), matching VoteButtons display
  const netVoteScore = upvotes - downvotes;

  return (
    <div className="flex flex-col h-full">
      <Link
        to={`/build-lists/${buildList.id}`}
        className="block hover:no-underline flex-grow"
      >
        <Card className="flex flex-col h-full hover:border-indigo-500 border-2 border-transparent transition-colors">
          <ImageWithPlaceholder
            srcUrl={buildList.image_url ?? null}
            altText={buildList.name}
            imageClassName="w-full h-40 object-cover rounded-md"
            containerClassName="w-full h-40 mb-4"
            fallbackText="No image"
          />
          <div className="flex-grow flex flex-col">
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-lg font-semibold text-indigo-400 flex-grow">
                {buildList.name}
              </h3>
              {/* Always show net vote score (upvotes - downvotes) */}
              <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                <svg
                  className={`w-4 h-4 ${
                    netVoteScore > 0
                      ? 'text-green-400'
                      : netVoteScore < 0
                        ? 'text-red-400'
                        : 'text-gray-400'
                  }`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fillRule="evenodd"
                    d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                <span
                  className={`text-sm font-semibold ${
                    netVoteScore > 0
                      ? 'text-green-400'
                      : netVoteScore < 0
                        ? 'text-red-400'
                        : 'text-gray-400'
                  }`}
                >
                  {netVoteScore > 0 ? '+' : ''}
                  {netVoteScore}
                </span>
              </div>
            </div>
            {buildList.description && (
              <p className="text-sm text-gray-400 mb-2 flex-grow">
                {buildList.description}
              </p>
            )}
            {carInfo && (
              <p className="text-xs text-gray-300 mb-2">
                {carInfo.make} {carInfo.model} {carInfo.generation_name}
              </p>
            )}
          </div>
        </Card>
      </Link>
      {showVoteButtons && (buildListWithVotes || voteSummary) && onVoteUpdate && (
        <div className="mt-2 pt-2 border-t border-gray-700">
          <VoteButtons
            entityId={buildList.id}
            upvotes={upvotes}
            downvotes={downvotes}
            userVote={userVote}
            onVoteUpdate={onVoteUpdate}
            voteApi={{
              voteOnEntity: (id, data) =>
                buildListVotesApi.voteOnBuildList(id, data),
              removeVote: (id) => buildListVotesApi.removeVote(id),
            }}
            size="sm"
          />
        </div>
      )}
    </div>
  );
};

export default BuildListItem;
