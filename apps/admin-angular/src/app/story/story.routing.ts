
import { StoryComponent } from './story.component';
import { StoriesComponent } from './stories.component';
import { TrainComponent } from './train.component';

export const StoryRoutes = [
    { component: StoriesComponent, name: 'Story', path: 'stories' },
    { component: StoryComponent, name: 'StoryNew', path: 'story/new' },
    { component: TrainComponent, name: 'StoryTrain', path: 'story/train/:id' },
    { component: StoryComponent, name: 'StoryEdit', path: 'story/:id' },
];
