import { Component, OnInit } from '@angular/core';
import { StoryService } from './story.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-stories',
  templateUrl: './stories.component.html',
  // styleUrls: ['./stories.component.css']
})
export class StoriesComponent implements OnInit {

  stories: any;

  constructor(private router: Router, public storyService: StoryService) { }

  ngOnInit() {
    this.storyService.getStories().then((s: any) => {
      this.stories = s;
    });
  }

  add() {
    this.router.navigate([`/story/new`]);
  }

  edit(story) {
    this.router.navigate([`/story/${story._id.$oid}`]);
  }

  train(story) {
    this.router.navigate([`/story/train/${story._id.$oid}`]);
  }

  delete(story) {
    if (confirm('Are u sure want to delete this story?')) {
      this.storyService.deleteStory(story._id.$oid).then((s: any) => {
        this.stories = s;
      });
    }
  }

  build(story) {
    this.storyService.buildStory(story._id.$oid).then((s: any) => {
      this.stories = s;
    });
  }

}
