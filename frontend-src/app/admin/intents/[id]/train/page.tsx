import TrainComponent from './TrainComponent';

export default function TrainPage({ params }: { params: { id: string } }) {
  return <TrainComponent id={params.id} />;
} 