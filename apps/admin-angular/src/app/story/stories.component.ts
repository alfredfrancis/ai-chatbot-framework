import { Component, OnInit } from '@angular/core';
import { StoryService } from './story.service';

@Component({
  selector: 'app-stories',
  templateUrl: './stories.component.html',
  // styleUrls: ['./stories.component.css']
})
export class StoriesComponent implements OnInit {

  stories: any;

  constructor(public storyService: StoryService) { }

  ngOnInit() {
    this.storyService.getStories().then((s: any) => {
      this.stories = s;
    });
  }

  edit(story) {
    // route change
   }

  train(story) {
   // route change
  }

  delete(story) {
    this.storyService.deleteStory(story._id.$od).then((s: any) => {
      this.stories = s;
    });
  }

  build(story) {
    this.storyService.buildStory(story._id.$od).then((s: any) => {
      this.stories = s;
    });
  }

}
